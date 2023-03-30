import asyncio
import json
import logging
import os
import secrets
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict

import aiohttp
import zmq
import zmq.asyncio
from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout

from owl_server import __version__, k8s
from owl_server.config import config, refresh

from ..schema import schema_pipeline
from .utils import safe_loop

MAX_PIPELINES = 99


class Scheduler:
    """Owl pipeline scheduler.

    The scheduler is responsible of communication between the user
    and the pipeline. It queues pipeline requests and runs them as
    resoures become available.
    """

    def __init__(self):
        self.logger = logging.getLogger("owl.daemon.scheduler")

        self.env = config.env  # enviroment variables from config
        self.heartbeat = config.heartbeat
        self._token = (
            secrets.token_hex()
        )  # secret token to use in communication between API and OWL

        self._smtp = config.pop("smtp", None)  # SMTP configuration

        self.pipelines = {}  # list of pipelines running
        self._max_pipe = config.max_pipelines or MAX_PIPELINES
        self.kube_metrics = {}
        self.pipe_metrics = {}
        config.pop(
            "dbi", None
        )  # database configuration, remove it as it is not used here

        self.is_started = False
        self._tasks = []  # list of coroutines
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.start())

    @property
    def namespace(self) -> str:
        """Return namespace of running Pod

        Returns
        -------
        Name of namespace where the current pod is running.
        """
        if not hasattr(self, "_namespace"):
            self._namespace = open(
                "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
            ).read()
        return self._namespace

    async def start(self):
        """Start scheduler.

        Start the following:

        - Check that we have correct Kubernetes credentials
        - Setup connection sockets.
        - HTTP client session for connections to the API.
        - Task for checking pipelines in the queue.
        - Task for checking pipelines status.
        - Task for receiving log messages.
        """
        if self.is_started:
            await asyncio.sleep(0)
            return

        self.logger.debug("Starting scheduler with %s", config)
        try:
            self.logger.debug("Testing Kubernetes credentials")
            await k8s.kube_test_credentials()
        except k8s.ConfigException as e:
            self.logger.critical("Unable to obtain Kubernetes configuration: %s", e)
            raise
        except k8s.ApiException as e:
            self.logger.critical("Exception when calling API: %s", e)
            raise

        self.session = aiohttp.ClientSession()

        try:
            await self._setup_sockets()
            await self._start_liveness_probe()
        except Exception as e:
            self.logger.critical("Unable to setup communication sockets: %s", e)

        await self.register_token()

        self._start_tasks()

        self.is_started = True
        self.logger.info("Owl scheduler started")

    def _start_tasks(self):
        """Add tasks to the loop."""
        self._tasks.extend(
            [
                asyncio.create_task(self.load_pipelines()),
                asyncio.create_task(self.scheduler_heartbeat()),
                asyncio.create_task(self.status_pipelines()),
                asyncio.create_task(self.clean_pipelines()),
                asyncio.create_task(self.cancel_pipelines()),
                asyncio.create_task(self.query_prometheus()),
                asyncio.create_task(self.logging_protocol()),
                asyncio.create_task(self.admin_commands()),
                asyncio.create_task(self.live_commands()),
            ]
        )

    @safe_loop()
    async def register_token(self):
        """Register token with the API."""
        path = f"/localapi/auth/token/register"
        res = await self._make_request(path, method="POST", data={"token": self._token})
        if res is not None:
            return True
        await asyncio.sleep(self.heartbeat)

    @safe_loop()
    async def scheduler_heartbeat(self):
        """Scheduler Heartbeat.

        Logs number of tasks and pipelines priodically.
        """
        await asyncio.sleep(self.heartbeat)
        self._tasks = [task for task in self._tasks if not task.done()]
        self.logger.debug(
            "Tasks %s, Pipelines %s", len(self._tasks), len(self.pipelines)
        )

    @safe_loop()
    async def logging_protocol(self):
        """Receive log lines in the ZMQ log address and
        logs them to the console.
        """
        topic, msg = await self.log_router.recv_multipart()
        msg = json.loads(msg.decode("utf8"))
        record = logging.makeLogRecord(msg)
        self.logger.handle(record)

    @safe_loop()
    async def query_prometheus(self):
        await asyncio.sleep(self.heartbeat)

        url = config.prometheus
        keys = [
            "kube_pod_container_resource_requests_cpu_cores",
            "kube_pod_container_resource_requests_memory_bytes",
            "machine_cpu_cores",
            "machine_memory_bytes",
        ]
        if not url:
            return True

        self.logger.debug("Querying Prometheus")
        url = f"{url}/api/v1/query"
        for query in keys:
            params = {"query": query}
            try:
                async with timeout(self.heartbeat):
                    async with self.session.get(url, params=params) as resp:
                        val = await resp.json()
            except ClientConnectorError:
                self.logger.error("Unable to connect to Prometheus at %s", url)
                return
            except asyncio.TimeoutError:
                self.logger.error("Prometheus request took too long. Cancelled")
                return

            val = val["data"]["result"]
            m = sum(float(item["value"][1]) for item in val)
            self.kube_metrics[query] = m
            self.logger.debug("Metric %s : %s", query, m)

    @safe_loop()
    async def load_pipelines(self):
        """Pipeline loader. Query pipelines from API and starts new."""
        await asyncio.sleep(self.heartbeat)

        # We can set maintenance mode at runtime
        if Path("/var/run/owl/nopipe").exists():
            self.logger.debug("Maintenaince mode. Pipelines not started.")
            return

        # Maximum number of pipelines at runtime
        if (maxpipe := Path("/var/run/owl/maxpipe")).exists():
            with maxpipe.open() as fh:
                self._max_pipe = int(fh.read()) or MAX_PIPELINES

        self.logger.debug("Checking for running pipelines")
        root = "/api/pipeline/list/running"
        pipelines = await self._make_request(root)

        for pipe in pipelines:
            if pipe["id"] in self.pipelines:
                continue
            await self.add_pipeline(pipe)

        self.logger.debug("Checking for pending pipelines")
        root = "/api/pipeline/list/pending"
        pipelines = await self._make_request(root)

        if not pipelines:
            return

        if "detail" in pipelines:
            self.logger.error(pipelines["detail"])
            return

        for pipe in pipelines:
            if pipe["id"] in self.pipelines:
                self.logger.debug("Pipeline already in list %s", pipe["id"])
                continue
            if len(self.pipelines) >= self._max_pipe:
                self.logger.info(
                    "Maximum number of pipelines reached (%s)", self._max_pipe
                )
                break

            try:
                pipe["config"] = schema_pipeline(pipe["config"])
            except Exception:
                self.logger.error("Unable to parse pipeline config %s", pipe["config"])
                await self.update_pipeline(pipe["id"], "ERROR")
                continue

            res = pipe["config"]["resources"]
            self.logger.info("Pipeline %s requesting %s", pipe["id"], res)
            try:
                res_cores = res["cpu"] * res["workers"]
                res_mem = res["memory"] * res["workers"]
            except KeyError:
                await self.update_pipeline(pipe["id"], "ERROR")
                continue
            if self.check_pipeline_resources(res_cores, res_mem):
                self.logger.info(
                    "Pipeline %s can run with requested resources", pipe["id"]
                )
            else:
                self.logger.warn("Not enough resources to run pipeline %s", pipe["id"])
                continue

            await self.start_pipeline(pipe)
            self.pipe_metrics[pipe["id"]] = {"cores": res_cores, "mem": res_mem}

    def check_pipeline_resources(self, res_cores, res_mem):
        with suppress(KeyError):
            avail_cores = (
                self.kube_metrics["machine_cpu_cores"]
                - self.kube_metrics["kube_pod_container_resource_requests_cpu_cores"]
            )
            avail_mem = (
                self.kube_metrics["machine_memory_bytes"]
                - self.kube_metrics["kube_pod_container_resource_requests_memory_bytes"]
            )
            used_pipe_cores = sum(v["cores"] for v in self.pipe_metrics.values())
            used_pipe_mem = sum(v["mem"] for v in self.pipe_metrics.values())
            avail_cores = avail_cores - used_pipe_cores
            avail_mem = avail_mem - used_pipe_mem * 1e6
            if (avail_cores < res_cores) or (avail_mem < res_mem * 1e6):
                return
        return True

    @safe_loop()
    async def cancel_pipelines(self):
        """Query for pipelines to cancel."""
        await asyncio.sleep(self.heartbeat)
        self.logger.debug("Checking for pipelines to cancel")
        root = "/api/pipeline/list/to_cancel"
        pipelines = await self._make_request(root)

        if not pipelines:
            return

        if "detail" in pipelines:
            self.logger.error(pipelines["detail"])
            return

        for pipe in list(pipelines):
            if pipe["id"] in self.pipelines:
                await self.stop_pipeline(pipe["id"], "CANCELLED")
            else:
                await self.update_pipeline(pipe["id"], "CANCELLED")

    async def stop(self):
        """Stop scheduler.

        One by one, cancel all tasks and pipelines running, in this order:

        - Pipelines. Their status is set back to PENDING.
        - Scheduler tasks.
        """
        # TODO: what we want really is that jobs are not stopped when the scheduler
        # is restarted. Save the status to a file and load it again.
        self.logger.debug("Stopping scheduler")
        if self.is_started:
            # for uid in list(self.pipelines):
            #     await self.stop_pipeline(uid, "PENDING")

            for task in self._tasks:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

            await self.session.close()
            self.is_started = False

        with suppress(Exception):
            self.pipe_router.close(linger=0)
            self.log_router.close(linger=0)
            self.live_router.close(linger=0)

        self.logger.info("Owl scheduler succesfully stopped")

    async def _setup_sockets(self):
        """Setup ZMQ sockets.

        We create the sockets for bidirectional communication with
        the pipelines (ROUTER-DEALER) and for receiving the logs
        (PUB-SUB).

        These are TCP sockets listening in the ports configured by
        environmental variables `OWL_SERVICE_PORT_PIPE` and
        `OWL_SERVICE_PORT_LOGS`.
        """
        self.ctx = zmq.asyncio.Context()

        # pipelines -- used for bidirectional messages with the pipelines
        self.pipe_addr = f"tcp://0.0.0.0:{self.env.OWL_SCHEDULER_SERVICE_PORT_PIPE}"
        self.pipe_router = self.ctx.socket(zmq.ROUTER)
        self.pipe_router.set(zmq.ROUTER_HANDOVER, 1)
        self.logger.debug("Pipeline router address: %s", self.pipe_addr)
        self.pipe_router.bind(self.pipe_addr)

        # administrative -- to get messages from the admin user through the API
        self.admin_addr = f"tcp://0.0.0.0:{self.env.OWL_SCHEDULER_SERVICE_PORT_ADMIN}"
        self.admin_router = self.ctx.socket(zmq.ROUTER)
        self.admin_router.set(zmq.ROUTER_HANDOVER, 1)
        self.logger.debug("Admin router address: %s", self.admin_addr)
        self.admin_router.bind(self.admin_addr)

        # logging -- to display logs from the API and Pipelines
        self.log_addr = f"tcp://0.0.0.0:{self.env.OWL_SCHEDULER_SERVICE_PORT_LOGS}"
        self.log_router = self.ctx.socket(zmq.SUB)
        # self.log_router.setsockopt(zmq.SUBSCRIBE, b"API")
        self.log_router.setsockopt(zmq.SUBSCRIBE, b"PIPELINE")
        self.log_router.bind(self.log_addr)
        self.logger.debug("Logs router address: %s", self.log_addr)
        await asyncio.sleep(0)

    async def _start_liveness_probe(self):
        # liveness and readiness probes
        self.live_addr = f"tcp://0.0.0.0:8080"
        self.live_router = self.ctx.socket(zmq.STREAM)
        self.live_router.bind(self.live_addr)
        self.logger.debug("Liveness probe address: %s", self.live_addr)

    async def _make_request(self, path, method=None, data=None):
        method = method or "GET"
        url = f"http://{self.env.OWL_API_SERVICE_HOST}:{self.env.OWL_API_SERVICE_PORT}{path}"
        headers = {"Authentication": f"owl {self._token}"}
        try:
            async with timeout(self.heartbeat):
                if method == "GET":
                    async with self.session.get(url, headers=headers) as resp:
                        response = await resp.json()
                elif method == "POST":
                    data = data or {}
                    async with self.session.post(
                        url, json=data, headers=headers
                    ) as resp:
                        response = await resp.json()
        except ClientConnectorError:
            self.logger.error("Unable to connect to API at %s", url)
            return
        except asyncio.TimeoutError:
            self.logger.error("API request took too long. Cancelled")
            return
        return response

    async def get_user(self, username):
        path = f"/api/auth/user/get/{username}"
        return await self._make_request(path)

    async def get_storage(self, pathname):
        pathname = pathname.replace("/", "__")
        path = f"/api/storage/get/{pathname}"
        return await self._make_request(path)

    async def add_pipeline(self, pipe: Dict[str, Any]):
        uid = int(pipe["id"])
        # user = pipe["username"]
        pipe_config = pipe["config"]
        jobname = f"pipeline-{uid}"
        status = "RUNNING"
        heartbeat = {"status": status}

        self.pipelines[uid] = {
            "last": time.monotonic(),
            "heartbeat": heartbeat,
            # "userinfo": userinfo[0],
            "job": status,
            "name": jobname,
            "uid": uid,
            "pdef": pipe_config,
        }

        self._tasks.append(asyncio.create_task(self.heartbeat_pipeline(uid)))

        await asyncio.sleep(0)

    async def start_pipeline(self, pipe: Dict[str, Any]):
        """Start a pipeline.

        Parameters
        ----------
        pipe
            pipeline definition
        """
        uid = int(pipe["id"])
        user = pipe["username"]
        pipe_config = pipe["config"]

        # TODO
        # check that pipeline (from pipeline definition) is active
        # if not pdef["active"]:
        #     self.logger.error("Pipeline not active %s", config["name"])
        #     raise Exception("Fingerprint failed")

        self.logger.debug("Starting pipeline ID %s", uid)

        # TODO: extract the information about the volumes to be mounted
        with open(f"/var/run/owl/conf/pipeline_{uid}.yaml", "w") as fh:
            fh.write(json.dumps(pipe_config))

        await self._tear_pipeline(uid)

        docker_image = f"{pipe['image']}:{pipe['tag']}"
        python = pipe_config["python"]

        env_vars = {
            "RUN_DEVELOP": "darkroom",
            "UID": f"{uid}",
            "JOBID": f"{uid}",
            "JOB_USER": user,
            "LOGLEVEL": config.loglevel,
            "PIPEDEF": json.dumps(pipe_config),
            "DOCKER_IMAGE": docker_image,
            "EXTRA_PIP_PACKAGES": pipe["package_name"],
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "NUMEXPR_MAX_THREADS": "1",
            "BLOSC_NOLOCK": "1",
            "BLOSC_NTHREADS": "1",
            "PYTHON_VIRTUALENV": python.get("virtualenv", "")
            or pipe_config.get("name", "default").replace("-", "_"),
            "RESET_VIRTUALENV": python.get("reset_virtualenv", ""),
        }

        # extra = config.pipeline.extraEnv or {}
        # [env_vars.update({d["name"]: d["value"]}) for d in extra]

        jobname = f"pipeline-{uid}"

        # Reload global config replacing USER
        # This works because we run in one thread and we do not run await until this is used
        # Needed to replace in the config
        os.environ.update({"JOB_USER": user})
        refresh()

        volumes = pipe["image_spec"].get("volumes", [])
        volume_mounts = pipe["image_spec"].get("volumeMounts", [])

        volumes += config["user"].get("volumes", [])
        volume_mounts += config["user"].get("volumeMounts", [])

        # TODO: check that user has permissions to access the volumes
        if "input_path" in pipe_config:
            st = await self.get_storage(pipe_config["input_path"])
            print("********", st)
            if "detail" not in st:
                volumes.append(st["spec"]["volume"])
                volume_mounts.append(st["spec"]["volumeMount"])

        if "output_path" in pipe_config:
            st = await self.get_storage(pipe_config["output_path"])
            if "detail" not in st:
                volumes.append(st["spec"]["volume"])
                volume_mounts.append(st["spec"]["volumeMount"])

        # self.logger.debug("Creating job %s with config %s", jobname, pipe)

        args = "owl-server pipeline"

        # print("************", pipe)
        body, status = await k8s.kube_create_job(
            jobname,
            docker_image,
            args=args.split(),
            # command=pipe["image_spec"]["command"],
            namespace=self.namespace,
            env_vars=env_vars,
            service_account_name="owl",
            retries=pipe_config["resources"].get("retries", 0),
            volumes=volumes,
            volume_mounts=volume_mounts,
        )

        self.logger.info(body)

        heartbeat = {"status": "RUNNING"}

        self.pipelines[uid] = {
            "last": time.monotonic(),
            "heartbeat": heartbeat,
            # "userinfo": userinfo[0],
            "job": status,
            "name": jobname,
            "uid": uid,
            "pdef": pipe_config,
        }

        await self.update_pipeline(uid, heartbeat["status"])

        self._tasks.append(asyncio.create_task(self.heartbeat_pipeline(uid)))

        return status

    async def stop_pipeline(self, uid: int, status: str):
        """Stop pipeline

        Parameters
        ----------
        uid : int
            Unique ID of pipeline
        status : str
            status of the pipeline
        """
        self.logger.debug(f"Stopping pipeline ID {uid}")
        await self.update_pipeline(uid, status)
        if uid in self.pipelines:
            await self._tear_pipeline(uid)
            pipeline = self.pipelines.pop(uid)
            pipeline["status"] = status

    async def _tear_pipeline(self, uid: int):
        if uid not in self.pipelines:
            await asyncio.sleep(0)
            return
        with suppress(Exception):
            jobname = self.pipelines[uid]["name"]
            self.logger.debug("Deleting job %s", jobname)
            await k8s.kube_delete_job(jobname, self.namespace)

    @safe_loop()
    async def heartbeat_pipeline(self, uid):
        """Check pipeline status.

        Send a periodic heartbeat status request to all running pipelines
        and act on result. Pipelines that report finished status are removed
        and those not responding the heartbeat request cancelled.
        """
        if uid not in self.pipelines:
            return True

        self.logger.debug("Sending heartbeat to pipeline %s", uid)
        await self.pipe_router.send_multipart([str(uid).encode("utf-8"), b"heartbeat"])
        await asyncio.sleep(self.heartbeat)

    @safe_loop()
    async def status_pipelines(self):
        uid, msg = await self.pipe_router.recv_multipart()
        uid, msg = int(uid.decode()), json.loads(msg.decode())
        self.logger.debug("Received heartbeat from pipeline %s : %s", uid, msg)
        self.pipelines[uid].update({"last": time.monotonic(), "heartbeat": msg})
        await self.update_pipeline(uid, msg["status"])

    def _set_maintance(self, value):
        fname = Path("/var/run/owl/nopipe")
        if value == "on":
            fname.touch()
            self.logger.info("Setting maintenance mode ON")
        elif value == "off":
            fname.unlink(missing_ok=True)
            self.logger.info("Setting maintenance mode OFF")

    def _set_maxpipe(self, value):
        fname = Path("/var/run/owl/maxpipe")
        try:
            maxpipe = int(value)
        except Exception:
            return
        if maxpipe > 0:
            with fname.open("w") as fh:
                fh.write(f"{maxpipe}")
            self.logger.info("Setting maximum pipelines to %s", maxpipe)
        else:
            fname.unlink(missing_ok=True)
            self.logger.info("Removing maximum pipelines constrain")

    def _set_heartbeat(self, value):
        try:
            heartbeat = int(value)
        except Exception:
            return
        self.heartbeat = heartbeat if heartbeat > 0 else config.heartbeat
        self.logger.info("Setting heartbeat to %s seconds", self.heartbeat)

    @safe_loop()
    async def live_commands(self):
        """Receive and execute live commands. Reuse for metrics."""
        req_id, msg = await self.live_router.recv_multipart()
        if "metrics" in msg.decode():
            metrics = [f"owl_pipelines_running {len(self.pipelines)}", ""]
            metrics_str = "\r\n".join(metrics)
            await self.live_router.send_multipart(
                [
                    req_id,
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n",
                    req_id,
                    metrics_str.encode(),
                    req_id,
                    b"",
                ]
            )

    @safe_loop()
    async def admin_commands(self):
        """Receive and execute administrative commands."""
        token, msg = await self.admin_router.recv_multipart()
        token, msg = token.decode(), json.loads(msg.decode())
        self.logger.debug("Received administrative command %s", msg)
        # In maintenance mode no new pipelines are scheduled
        if "maintenance" in msg:
            self._set_maintance(msg["maintenance"])
        # Limit maximum number of pipelines that can be run at the same time
        elif "maxpipe" in msg:
            self._set_maxpipe(msg["maxpipe"])
        # Configure heartbeat
        elif "heartbeat" in msg:
            self._set_heartbeat(msg["heartbeat"])
        # Cancel pipeline
        elif "stop_pipeline" in msg:
            try:
                uid = int(msg["jobid"])
                status = "CANCELLED"
            except Exception:
                return
            if uid in self.pipelines:
                await self.stop_pipeline(uid, status)
            else:
                await self.update_pipeline(uid, status)

    @safe_loop()
    async def clean_pipelines(self):
        for pipe in list(self.pipelines):  # list -> avoid dictionary change
            last = self.pipelines[pipe]["last"]
            status = self.pipelines[pipe]["heartbeat"]["status"]
            if status in ["FINISHED"]:
                self.logger.debug("Pipeline completed %s", pipe)
                await self.stop_pipeline(pipe, status)
            # elif status in ["ERROR"]:
            # self.logger.debug("Pipeline %s returned status %s", pipe, status)
            # We do not stop the pipeline here to allow for
            # jobs to rerun
            # self.logger.debug("Stopping pipeline %s with status %s", pipe, status)
            # await self.stop_pipeline(pipe, status)
            elif time.monotonic() - last > 10 * self.heartbeat:
                self.logger.debug("Heartbeat not received. Stopping pipeline %s", pipe)
                status = "ERROR"
                await self.stop_pipeline(pipe, status)
        await asyncio.sleep(self.heartbeat)

    async def update_pipeline(self, uid: int, status: str):
        """Update pipeline status.

        Parameters
        ----------
        uid
            pipeline id
        status
            status to set the pipeline to
        response
            heartbeat response
        """
        await asyncio.sleep(0)

        self.logger.info("Updating pipeline %s - %s", uid, status)
        data = {"status": status}
        with suppress(KeyError):
            data["heartbeat"] = self.pipelines[uid]["heartbeat"]

        root = f"/api/pipeline/update/{uid}"
        msg = await self._make_request(root, method="POST", data=data)

        if not msg:
            return

        if "detail" in msg:
            self.logger.error(msg["detail"])
            return

        with suppress(KeyError):
            if status not in ["PENDING"]:
                self.pipe_metrics.pop(uid)

    async def get_pipedef(self, name: str):
        """Retrieve pipeline definion file from API

        Parameters
        ----------
        name
            name of the pipeline
        """
        self.logger.debug("Getting pipeline definition for %s", name)
        root = f"/api/pdef/get/{name}"
        res = await self._make_request(root)

        if not res:
            return

        if "detail" in res:
            self.logger.error("Pipeline not found %s", name)
            return

        return res
