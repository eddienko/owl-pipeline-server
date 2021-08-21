from distributed import WorkerPlugin
from loky import ProcessPoolExecutor

# from concurrent.futures import ProcessPoolExecutor


class LoggingPlugin(WorkerPlugin):
    def __init__(self, config):
        self.config = config

    def setup(self, worker):
        import logging.config

        logging.config.dictConfig(self.config)


class ProcessPoolPlugin(WorkerPlugin):
    def setup(self, worker):
        executor = ProcessPoolExecutor(max_workers=worker.nthreads)
        worker.executors["processes"] = executor
