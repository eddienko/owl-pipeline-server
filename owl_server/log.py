import logging.config
import logging.handlers
import os
from contextlib import suppress

import coloredlogs
import yaml
import zmq

logconf = """
version: 1
disable_existing_loggers: False
handlers:
  console:
    class: logging.StreamHandler
    formatter: standard
    stream: 'ext://sys.stderr'
  console_pipeline:
    class: logging.StreamHandler
    formatter: pipeline
    stream: 'ext://sys.stderr'
  file_pipeline:
    class: owl_server.log.TimeRotatingFileHandler
    filename: /var/run/owl/logs/pipeline_${JOBID}.log
    formatter: pipeline
    backupCount: 7
  console_scheduler:
    class: logging.StreamHandler
    formatter: scheduler
    stream: 'ext://sys.stderr'
  file_scheduler:
    class: owl_server.log.TimeRotatingFileHandler
    filename: /var/run/owl/logs/scheduler.log
    formatter: scheduler
    when: "d"
    backupCount: 7
  console_api:
    class: logging.StreamHandler
    formatter: api
    stream: 'ext://sys.stderr'
  file_api:
    class: owl_server.log.TimeRotatingFileHandler
    filename: /var/run/owl/logs/api.log
    formatter: scheduler
    when: "d"
    backupCount: 7
formatters:
  pipeline:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s PIPELINE %(levelname)s %(name)s %(funcName)s - %(message)s"
  scheduler:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s SCHEDULER %(levelname)s %(name)s %(funcName)s - %(message)s"
  api:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s API %(levelname)s %(name)s %(funcName)s - %(message)s"
  standard:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s %(levelname)s %(name)s %(funcName)s - %(message)s"
loggers:
  owl.daemon.pipeline:
    handlers: [console_pipeline, file_pipeline]
    level: ${LOGLEVEL}
    propagate: false
  owl.daemon.scheduler:
    handlers: [console_scheduler, file_scheduler]
    level: ${LOGLEVEL}
    propagate: false
  owl.cli:
    handlers: [console]
    level: ${LOGLEVEL}
    propagate: false
  root:
    handlers: [console]
    level: INFO
    propagate: false
  uvicorn.error:
    handlers: [console_api, file_api]
    level: ${LOGLEVEL}
    propagate: false
  uvicorn.access:
    handlers: [console_api, file_api]
    level: ${LOGLEVEL}
    propagate: false
  uvicorn:
    handlers: [console_api, file_api]
    level: ${LOGLEVEL}
    propagate: false
"""


def initlog():
    """Configure logging.
    """
    log_config = yaml.safe_load(logconf)
    logging.config.dictConfig(log_config)


def logging_iteractive():
    """Helper function for iteractive sessions.
    """
    log_config = yaml.safe_load(logconf)
    initlog(log_config)


class TimeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Time rotating file handler.

    It makes the base directory if it does not exist.

    Parameters
    ----------
    filename
        name of file to log to
    """

    def __init__(self, filename: str, **kwargs):
        path = os.path.dirname(filename)
        os.makedirs(path, exist_ok=True)
        super().__init__(filename, **kwargs)

    def open(self):
        super()._open()


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Time rotating file handler.

    It makes the base directory if it does not exist.

    Parameters
    ----------
    filename
        name of file to log to
    """

    def __init__(self, filename: str, **kwargs):
        path = os.path.dirname(filename)
        os.makedirs(path, exist_ok=True)
        super().__init__(filename, **kwargs)
        self.doRollover()

    def open(self):
        super()._open()


class ColoredFormatter(coloredlogs.ColoredFormatter):
    """Colored formatter for logs.

    Parameters
    ----------
    fmt
        log formatting string
    datefmt
        format string for dates
    style
        style of log format
    """

    def __init__(self, fmt: str, datefmt: str, style: str):
        super().__init__(fmt, datefmt, style=style)


class PUBHandler(logging.Handler):
    def __init__(self, address, topic):
        with suppress(Exception):
            self.ctx = zmq.Context()
            self.socket = self.ctx.socket(zmq.PUB)
            self.socket.connect(address)
            self.topic = topic
        super().__init__()

    def emit(self, record):
        msg = self.format(record).encode("utf-8")
        with suppress(Exception):
            topic = f"{self.topic}.{record.levelname}".encode("utf-8")
            self.socket.send_multipart([topic, msg])
