import asyncio
import json
import logging
import pickle
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict

import aiohttp
import zmq
import zmq.asyncio
from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from owl_server import k8s
from owl_server.config import config

from .utils import safe_loop

MAX_PIPELINES = 1


class Scheduler:
    """Owl pipeline scheduler.

    The scheduler is responsible of communication between the user
    and the pipeline. It queues pipeline requests and runs them as
    resoures become available.
    """

    def __init__(self):
        self.logger = logging.getLogger("owl.daemon.scheduler")

        self.env = config.env  # enviroment variables from config
        self._token = config.pop("token")  # secret token to use in communication between API and OWL

        self.pipelines = {}  # list of pipelines running
        self._max_pipe = MAX_PIPELINES

        config.pop("dbi")   # database configuration, remove it as it is not used here

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

        self._start_tasks()

        self.is_started = True
        self.logger.info("Owl scheduler started")

    def _start_tasks(self):
        """Add tasks to the loop.
        """
        self._tasks.extend(
            [
                asyncio.create_task(self.load_pipelines()),
                asyncio.create_task(self.scheduler_heartbeat()),
                asyncio.create_task(self.status_pipelines()),
                asyncio.create_task(self.clean_pipelines()),
                asyncio.create_task(self.cancel_pipelines()),
            ]
        )

    @safe_loop()
    async def scheduler_heartbeat(self):
        """Scheduler Heartbeat.

        Logs number of tasks and pipelines priodically.
        """
        await asyncio.sleep(config.heartbeat)
        self._tasks = [task for task in self._tasks if not task.done()]
        self.logger.debug("Tasks %s, Pipelines %s", len(self._tasks), len(self.pipelines))

    @safe_loop()
    async def load_pipelines(self):
        """Pipeline loader. Query pipelines from API and starts new.
        """
        await asyncio.sleep(config.heartbeat)

        # We can set maintenance mode at runtime
        if Path("/var/run/owl/nopipe").exists():
            self.logger.debug("Maintenaince mode. Pipelines not started.")
            return

        # Maximum number of pipelines at runtime
        if (maxpipe := Path("/var/run/owl/maxpipe")).exists():
            with maxpipe.open() as fh:
                self._max_pipe = int(fh.read())

        # Check for pending pipelines
        root = "/api/pipeline/list/pending"
        url = f"http://{self.env.OWL_API_SERVICE_HOST}:{self.env.OWL_API_SERVICE_PORT}{root}"
        headers = {"Authentication": f"owl {self._token}"}

        self.logger.debug("Checking for pipelines")
        try:
            async with timeout(config.heartbeat):
                async with self.session.get(url, headers=headers) as resp:
                    pipelines = await resp.json()
        except ClientConnectorError:
            self.logger.error("Unable to connect to API at %s", url)
            return
        except asyncio.TimeoutError:
            self.logger.error("API request took too long. Cancelled")
            return

        if "detail" in pipelines:
            self.logger.error(pipelines["detail"])
            return

        for pipe in pipelines:
            if pipe["id"] in self.pipelines:
                self.logger.debug("Pipeline already in list %s", pipe["id"])
                continue
            if len(self.pipelines) >= self._max_pipe:
                self.logger.info("Maximum number of pipelines reached (%s)", self._max_pipe)
                break

            await self.start_pipeline(pipe)

    @safe_loop()
    async def cancel_pipelines(self):
        """Query for pipelines to cancel.
        """
        await asyncio.sleep(config.heartbeat)

        # Check for pending pipelines
        root = "/api/pipeline/list/to_cancel"
        url = f"http://{self.env.OWL_API_SERVICE_HOST}:{self.env.OWL_API_SERVICE_PORT}{root}"
        headers = {"Authentication": f"owl {self._token}"}

        self.logger.debug("Checking for pipelines to cancel")
        try:
            async with timeout(config.heartbeat):
                async with self.session.get(url, headers=headers) as resp:
                    pipelines = await resp.json()
        except ClientConnectorError:
            self.logger.error("Unable to connect to API at %s", url)
            return
        except asyncio.TimeoutError:
            self.logger.error("API request took too long. Cancelled")
            return

        if "detail" in pipelines:
            self.logger.error(pipelines["detail"])
            return

        for pipe in list(pipelines):
            if pipe["id"] in self.pipelines:
                await self.stop_pipeline(pipe["id"], "CANCELLED")

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
            for uid in self.pipelines:
                await self.stop_pipeline(uid, "PENDING")
            # self.logger.info("Saving pipelines status")
            # with open("/var/run/owl/pipelines.pkl", "w") as fh:
            #     pickle.dump(self.pipelines, fh)

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

        # logging -- to display logs from the API and Pipelines
        self.log_addr = f"tcp://0.0.0.0:{self.env.OWL_SCHEDULER_SERVICE_PORT_LOGS}"
        self.log_router = self.ctx.socket(zmq.SUB)
        self.log_router.setsockopt(zmq.SUBSCRIBE, b"api")
        self.log_router.setsockopt(zmq.SUBSCRIBE, b"pipeline")
        self.log_router.bind(self.log_addr)
        self.logger.debug("Logs router address: %s", self.log_addr)
        await asyncio.sleep(0)

    async def _start_liveness_probe(self):
        # liveness and readiness probes
        self.live_addr = f"tcp://0.0.0.0:{8080}"
        self.live_router = self.ctx.socket(zmq.REP)
        self.live_router.bind(self.live_addr)
        self.logger.debug("Liveness probe address: %s", self.live_addr)

    async def start_pipeline(self, pipe: Dict[str, Any]):
        """Start a pipeline.

        Parameters
        ----------
        pipe
            pipeline definition
        """
        uid = pipe["id"]
        user = pipe["user"]
        pipe_config = pipe["config"]

        pdef = await self.get_pipedef(pipe_config["name"])
        if pdef is None:
            self.logger.error("Failed to obtain fingerprint for pipeline %s", config["name"])
            raise Exception("Fingerprint failed")

        self.logger.debug("Starting pipeline ID %s", uid)

        with open(f"/var/run/owl/conf/pipeline_{uid}.yaml", "w") as fh:
            fh.write(json.dumps(pipe_config))
        
        await self._tear_pipeline(uid)

        command = f"owl-server pipeline --conf /var/run/owl/conf/pipeline_{uid}.yaml"

        env_vars = {
            "UID": uid,
            "JOBID": uid,
            "USER": user,
            "LOGLEVEL": config.loglevel,
            "DASK_IMAGE_SPEC": self.env.OWL_IMAGE_SPEC,
            "OWL_IMAGE_SPEC": self.env.OWL_IMAGE_SPEC,
            "EXTRA_PIP_PACKAGES": pdef["extra_pip_packages"],
        }
        
        self.logger.debug("Creating job %s in namespace %s", uid, self.namespace)
        status = await k8s.kube_create_job(
            f"pipeline-{uid}",
            self.env.OWL_IMAGE_SPEC,
            command=command,
            namespace=self.namespace,
            extraConfig=config.pipeline,
            env_vars=env_vars,
        )

        heartbeat = {"status": "STARTING"}
        self.pipelines[uid] = {"last": time.monotonic(), "heartbeat": heartbeat, "job": status}
        await self.update_pipeline(uid, heartbeat["status"])
        self._tasks.append(asyncio.create_task(self.heartbeat_pipeline(uid)))

        print(config.pipeline)
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

    async def _tear_pipeline(self, uid: int):
        if uid not in self.pipelines:
            await asyncio.sleep(0)
            return
        with suppress(Exception):
            await k8s.kube_delete_job(f"pipeline-{uid}", self.namespace)
        self.pipelines.pop(uid)

    @safe_loop()
    async def heartbeat_pipeline(self, uid):
        """Check pipeline status.

        Send a periodic heartbeat status request to all running pipelines
        and act on result. Pipelines that report finished status are removed
        and those not responding the heartbeat request cancelled.
        """
        if uid not in self.pipelines:
            return True
        if not self.pipelines[uid].get("received", True):
            self.logger.debug("Waiting for heartbeat from pipeline %s", uid)
            return
        self.logger.debug("Sending heartbeat to pipeline %s", uid)
        await self.pipe_router.send_multipart([str(uid).encode("utf-8"), b"heartbeat"])
        self.pipelines[uid]["received"] = "False"
        await asyncio.sleep(config.heartbeat)

    @safe_loop()
    async def status_pipelines(self):
        uid, msg = await self.pipe_router.recv_multipart()
        uid, msg = int(uid.decode()), json.loads(msg.decode())
        self.logger.debug("Received heartbeat from pipeline %s : %s", uid, msg)
        self.pipelines[uid].update({"last": time.monotonic(), "heartbeat": msg, "received": True})
        await self.update_pipeline(uid, msg["status"])

    @safe_loop()
    async def clean_pipelines(self):
        for pipe in list(self.pipelines):  # list -> avoid dictionary change
            last = self.pipelines[pipe]["last"]
            status = self.pipelines[pipe]["heartbeat"]["status"]
            if status in ["FINISHED"]:
                self.logger.debug("Pipeline completed %s", pipe)
                await self.stop_pipeline(pipe, status)
            elif status in ["ERROR"]:
                self.logger.debug("Stopping pipeline %s with status %s", pipe, status)
                await self.stop_pipeline(pipe, status)
            elif time.monotonic() - last > 5 * config.heartbeat:
                self.logger.debug("Heartbeat not received. Stopping pipeline %s", pipe)
                status = "ERROR"
                await self.stop_pipeline(pipe, status)
        await asyncio.sleep(config.heartbeat)

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
        root = f"/api/pipeline/update/{uid}"
        url = f"http://{self.env.OWL_API_SERVICE_HOST}:{self.env.OWL_API_SERVICE_PORT}{root}"
        headers = {"Authentication": f"owl {self._token}"}

        try:
            async with timeout(config.heartbeat):
                async with self.session.post(url, json=data, headers=headers) as resp:
                    msg = await resp.json()
        except ClientConnectorError:
            self.logger.error("Unable to connect to API at %s", url)
            return
        except asyncio.TimeoutError:
            self.logger.error("API request took too long. Cancelled")
            return

        if "detail" in msg:
            self.logger.error(msg["detail"])
            return
            
    async def get_pipedef(self, name: str):
        """Retrieve pipeline definion file from API

        Parameters
        ----------
        name
            name of the pipeline
        """
        root = f"/api/pdef/get/{name}"
        url = f"http://{self.env.OWL_API_SERVICE_HOST}:{self.env.OWL_API_SERVICE_PORT}{root}"
        headers = {"Authentication": f"owl {self._token}"}

        self.logger.debug("Getting pipeline definition for %s", name)
        try:
            async with timeout(config.heartbeat // 2):
                async with self.session.get(
                    url, headers=headers
                ) as resp:
                    res = await resp.json()
        except ClientConnectorError:
            self.logger.error("Unable to connect to API at %s", url)
            return
        except asyncio.TimeoutError:
            self.logger.error("API request took too long. Cancelled")
            return

        if "detail" in res:
            self.logger.error("Pipeline not found %s", name)
            return

        return res