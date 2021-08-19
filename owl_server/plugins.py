from distributed import WorkerPlugin


class LoggingPlugin(WorkerPlugin):
    def __init__(self, config):
        self.config = config

    def setup(self, worker):
        import logging.config

        logging.config.dictConfig(self.config)
