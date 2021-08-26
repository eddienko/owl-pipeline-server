import asyncio
import concurrent.futures
import json
import logging
import os
import time
from contextlib import suppress

import zmq
import zmq.asyncio
from dask.config import config as dask_config
from dask_kubernetes import KubeCluster
from distributed import Client
from owl_server import pipelines
from owl_server.config import config
from voluptuous import Invalid, MultipleInvalid

from .utils import safe_loop


class Pipeline:
    """Pipeline worker.

    The pipeline worker is started by the scheduler when a pipeline needs to
    be run. This worker runs the pipeline code, starting the swarm containers if
    necessart and is responsible of following the execution status and cleaning up.

    The process of running a pipeline is then as follows:

    1. The main scheduler starts a pipeline worker and sends the pipeline definition
       file and extra configuration needed.
    2. The worker loads the pipeline code and validates it against its schema.
    3. If running in swarm mode, the cluster starts the docker containers as requested.
    4. The worker starts a separate thread and runs the pipeline code.
    5. The main thread listens for heartbeat connections from the scheduler and waits for
       pipeline completion.
    6. The worker responds with the pipeline completion result to the scheduler.
    7. The scheduler stops the pipeline worker.

    Parameters
    ----------
    conf
        configuration
    logconf
        logging configuration
    """

    def __init__(self, pdef):
        self.logger = logging.getLogger("owl.daemon.pipeline")
        self.uid = os.environ.get("UID")
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self.pdef = pdef
        self.name = self.pdef["name"]
        self.info = {"started": time.time(), "version": ""}
        self._tasks = []
        self.running = False
        self.status = "STARTING"
        self._watch = time.monotonic()

        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.start())

    @property
    def elapsed(self):
        return time.monotonic() - self._watch

    async def start(self):
        self.logger.info("Starting pipeline ID %s with %s", self.uid, self.pdef)

        await self._setup_sockets()

        self._tasks.append(asyncio.ensure_future(self.heartbeat()))

        try:
            await self.loop.run_in_executor(self.executor, self.check_pipeline)
        except (AttributeError, Invalid, MultipleInvalid) as e:
            self.logger.critical(
                "Unable to load pipeline %s: %s", self.name, e, exc_info=True
            )
            self.status = "ERROR"
            return

        await self.start_dask_cluster()

        func = getattr(pipelines, self.name)
        self.logger.info(f"Running {func!r} with {self.pdef}")
        self.proc = self.loop.run_in_executor(
            self.executor, func, self.pdef, self.cluster
        )
        self.proc.add_done_callback(self.pipeline_done)
        self._tasks.append(self.proc)
        self._tasks.append(asyncio.ensure_future(self.get_scheduler_info()))

        self.status = "RUNNING"
        self.running = True

    async def run(self):
        while self.running:
            await asyncio.sleep(10)

        return self.status

    def pipeline_done(self, future: asyncio.Future):
        self.logger.info("Pipeline ID %s finished", self.uid)
        if e := future.exception():
            self.logger.critical("Failed to run pipeline %s", e)
            self.status = "ERROR"
        else:
            self.status = "FINISHED"

    def close(self):
        asyncio.ensure_future(self.stop())

    async def start_dask_cluster(self):
        self.logger.info("Starting Dask cluster")
        self.dask_config()
        nworkers = self.pdef["resources"]["workers"]
        self.cluster = await KubeCluster(asynchronous=True)
        self.cluster.adapt(minimum=nworkers, maximum=nworkers)
        while len(self.cluster.scheduler_info["workers"]) != nworkers:
            await asyncio.sleep(1)
        self.logger.debug("Scheduler address: %s", self.cluster.scheduler_address)

    def dask_config(self):
        resources = self.pdef["resources"]
        worker = config.dask.kubernetes["worker-template"]["spec"]["containers"][0]
        nthreads = resources["threads"]
        nprocs = resources["processes"]
        memory = resources["memory"]
        args = [
            "dask-worker",
            "--nthreads",
            f"{nthreads}",
            "--nprocs",
            f"{nprocs}",
            "--memory-limit",
            f"{memory}GB",
            "--death-timeout",
            "60",
        ]
        worker["args"] = args
        worker["resources"] = {
            "limits": {
                "cpu": f"{nthreads*nprocs}",
                "memory": f"{memory}G",
            },
            "requests": {
                "cpu": f"{nthreads*nprocs}",
                "memory": f"{memory}G",
            },
        }

        for k in ["name", "scheduler-template", "worker-template"]:
            dask_config["kubernetes"][k] = config.dask.kubernetes[k]

    async def _setup_sockets(self):
        self.owl_host = os.environ.get("OWL_SCHEDULER_SERVICE_HOST")
        self.pipe_port = os.environ.get("OWL_SCHEDULER_SERVICE_PORT_PIPE")
        self.pipe_addr = f"tcp://{self.owl_host}:{self.pipe_port}"
        self.logger.debug("Connecting to %s", self.pipe_addr)
        self.ctx = zmq.asyncio.Context()

        self.pipe_socket = self.ctx.socket(zmq.DEALER)
        self.pipe_socket.setsockopt(zmq.IDENTITY, self.uid.encode("utf-8"))
        self.pipe_socket.connect(self.pipe_addr)

        await asyncio.sleep(0)

    @safe_loop()
    async def heartbeat(self):
        await self.pipe_socket.recv()
        self.logger.debug("Pipeline %s: heartbeat received", self.uid)
        msg = {
            "status": self.status,
            "started": self.info["started"],
            "elapsed": self.elapsed,
            "version": self.info["version"],
            "last_heartbeat": time.time(),
        }

        with suppress(Exception):
            msg.update(
                {
                    "dask_scheduler": {
                        "address": self.cluster.scheduler_address,
                        "info": self.cluster.scheduler_info,
                    }
                }
            )

        await self.pipe_socket.send(json.dumps(msg).encode("utf-8"))

        if self.status in ["ERROR", "FINISHED"]:
            self.close()
            return True

    async def stop(self):
        """Stop pipeline worker.

        All tasks started by `start` are now cancelled.
        """
        self.logger.info("Stopping pipeline ID %s", self.uid)
        if self.running:
            self.running = False

            with suppress(Exception):
                await self.cluster.close()

            for task in self._tasks:
                task.cancel()
                with suppress(Exception):
                    await task

            with suppress(Exception):
                self.pipe_socket.close(linger=0)

    @safe_loop()
    async def get_scheduler_info(self):
        if self.running:
            async with Client(self.cluster, asynchronous=True) as client:
                scheduler_info = client.scheduler_info()
            self.info["scheduler"] = scheduler_info
            self.logger.debug("Scheduler info : %s", scheduler_info)

            await self.delete_unresponsive_workers()
        await asyncio.sleep(config.heartbeat)

    async def delete_unresponsive_workers(self):
        now = time.time()
        workers = self.info["scheduler"]["workers"]
        last_seen = {v['id']: now - v['last_seen'] for v in workers.values()}
        for k, v in last_seen.items():
            if v > 5 * config.heartbeat:
                self.logger.warn("Restarting unresponsive worker %s", k)
                await self.delete_worker(k)
        await asyncio.sleep(0.1)

    async def delete_worker(self, n):
        pod = self.cluster.workers[n]
        await pod.close()

    def check_pipeline(self):
        self.logger.debug("Loading pipeline %s", self.name)
        self.func = getattr(pipelines, self.name)
        self.logger.debug("Loaded pipeline %s", self.name)
        self.info["version"] = self.func.__version__
