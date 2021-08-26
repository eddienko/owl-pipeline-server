import json
import logging.config
import logging.handlers
import os
from contextlib import suppress

import coloredlogs
import yaml
import zmq

from . import utils  # noqa: F401

logconf = {
    "api": """
version: 1
disable_existing_loggers: False
filters:
  filter_api:
    (): owl_server.log.LogFilter
    topic: API
handlers:
  console:
    class: owl_server.log.StreamHandler
    formatter: standard
    stream: 'ext://sys.stderr'
    filters: ["filter_api"]
  file:
    class: owl_server.log.TimeRotatingFileHandler
    filename: /var/run/owl/logs/api.log
    formatter: standard
    when: "d"
    backupCount: 7
    filters: ["filter_api"]
formatters:
  standard:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s %(topic)s %(levelname)s %(name)s %(funcName)s - %(message)s"
loggers:
  owl.cli:
    handlers: [console]
    level: ${LOGLEVEL}
    propagate: false
  root:
    handlers: [console]
    level: INFO
    propagate: false
  uvicorn.error:
    handlers: [console, file]
    level: ${LOGLEVEL}
    propagate: false
  uvicorn.access:
    handlers: [console, file]
    level: ${LOGLEVEL}
    propagate: false
  uvicorn:
    handlers: [console, file]
    level: ${LOGLEVEL}
    propagate: false
""",
    "scheduler": """
version: 1
filters:
  filter_scheduler:
    (): owl_server.log.LogFilter
    topic: SCHEDULER
handlers:
  console:
    class: owl_server.log.StreamHandler
    formatter: standard
    stream: 'ext://sys.stderr'
    filters: ["filter_scheduler"]
  file:
    class: owl_server.log.TimeRotatingFileHandler
    filename: /var/run/owl/logs/scheduler.log
    formatter: standard
    when: "d"
    backupCount: 7
    filters: ["filter_scheduler"]
formatters:
  standard:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s %(topic)s %(levelname)s %(name)s %(funcName)s - %(message)s"
loggers:
  owl.daemon.scheduler:
    handlers: [console, file]
    level: ${LOGLEVEL}
    propagate: false
  owl.cli:
    handlers: [console, file]
    level: ${LOGLEVEL}
    propagate: false
  root:
    handlers: [console, file]
    level: INFO
    propagate: false
""",
    "cli": """
version: 1
disable_existing_loggers: False
filters:
  filter_console:
    (): owl_server.log.LogFilter
    topic: CONSOLE
handlers:
  console:
    class: owl_server.log.StreamHandler
    formatter: standard
    stream: 'ext://sys.stderr'
    filters: ["filter_console"]
formatters:
  standard:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s %(topic)s %(levelname)s %(name)s %(funcName)s - %(message)s"
loggers:
  owl.cli:
    handlers: [console]
    level: ${LOGLEVEL}
    propagate: false
""",
    "pipeline": """
version: 1
disable_existing_loggers: False
filters:
  filter_pipeline:
    (): owl_server.log.LogFilter
    topic: PIPELINE
    jobid: ${JOBID}
handlers:
  console:
    class: owl_server.log.StreamHandler
    formatter: standard
    stream: 'ext://sys.stderr'
    filters: ["filter_pipeline"]
  file:
    class: owl_server.log.TimeRotatingFileHandler
    filename: /tmp/pipeline.log
    formatter: standard
    when: "d"
    backupCount: 7
    filters: ["filter_pipeline"]
  zmq:
    class: owl_server.log.PUBHandler
    address: tcp://owl-scheduler:7002
    formatter: standard
    filters: ["filter_pipeline"]
formatters:
  standard:
    class: owl_server.log.ColoredFormatter
    format: "%(asctime)s %(topic)s %(levelname)s %(name)s %(funcName)s - %(message)s"
loggers:
  owl.daemon.pipeline:
    handlers: [console, file, zmq]
    level: ${LOGLEVEL}
    propagate: false
  owl.cli:
    handlers: [console, file, zmq]
    level: ${LOGLEVEL}
    propagate: false
  distributed:
    handlers: [console, file, zmq]
    level: INFO
    propagate: false
  root:
    handlers: [console, file, zmq]
    level: INFO
    propagate: false
""",
}


def initlog(val):
    """Configure logging."""
    log_config = yaml.safe_load(logconf[val])
    logging.config.dictConfig(log_config)
    return log_config


def logging_iteractive():
    """Helper function for iteractive sessions."""
    log_config = yaml.safe_load(logconf)
    initlog(log_config)


class LogFilter(logging.Filter):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def filter(self, record):
        flag = True
        for k, v in self.kwargs.items():
            try:
                flag = flag and (getattr(record, k) == v)
            except AttributeError:
                setattr(record, k, v)
        return flag


class StreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)


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


class PipelineFileHandler(logging.FileHandler):
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

    def format(self, record):
        try:
            record.topic
        except AttributeError:
            record.topic = ""
        return super().format(record)


class PUBHandler(logging.Handler):
    def __init__(self, address):
        super().__init__()
        self.address = address
        self.socket = None

    def createSocket(self):
        with suppress(zmq.ZMQError):
            self.ctx = zmq.Context()
            self.socket = self.ctx.socket(zmq.PUB)
            self.socket.connect(self.address)

    def makeJSON(self, record):
        ei = record.exc_info
        if ei:
            # just to get traceback text into record.exc_text ...
            self.format(record)
        d = dict(record.__dict__)
        d["msg"] = record.getMessage()
        d["args"] = None
        d["exc_info"] = None
        # delete 'message' if present: redundant with 'msg'
        d.pop("message", None)
        return json.dumps(d)

    def send(self, s, topic):
        if self.socket is None:
            self.createSocket()
        if self.socket:
            topic = f"{topic}".encode("utf-8")
            msg = s.encode("utf-8")
            self.socket.send_multipart([topic, msg])

    def handleError(self, record):
        self.socket.close(linger=0)
        self.socket = None

    def emit(self, record):
        try:
            s = self.makeJSON(record)
            self.send(s, record.topic)
        except Exception:
            self.handleError(record)

    def release(self):
        with suppress(Exception):
            self.lock.release()

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
            self.release()
