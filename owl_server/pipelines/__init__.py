import logging
import os
import shutil
import traceback
from contextlib import suppress
from functools import wraps
from pathlib import Path
from typing import Callable, Dict

import pkg_resources
import voluptuous as vo
import yaml
from distributed import Client
from owl_server.log import logconf
from owl_server.plugins import LoggingPlugin, ProcessPoolPlugin

logger = logging.getLogger("owl.daemon.scheduler")

PIPELINES = {}


def _import_pipelines():
    for e in pkg_resources.iter_entry_points("owl.pipelines"):
        f = e.load()
        try:
            schema = f.schema
        except AttributeError:
            schema = None
        PIPELINES[e.name] = register_pipeline(validate=schema)(f)


class register_pipeline:
    """Register a pipeline."""

    def __init__(self, *, validate: vo.Schema = None):
        self.schema = validate
        if self.schema is not None:
            self.schema.extra = vo.REMOVE_EXTRA

    def __call__(self, func: Callable):
        name = func.__name__

        @wraps(func)
        def wrapper(config: Dict, cluster=None):

            if self.schema is not None:
                _config = self.schema(config)
            else:
                _config = config

            if cluster is not None:
                try:
                    client = Client(cluster.scheduler_address)
                except Exception:
                    traceback_str = traceback.format_exc()
                    raise Exception(
                        "Error occurred. Original traceback " "is\n%s\n" % traceback_str
                    )
                c = yaml.safe_load(logconf["pipeline"])
                client.register_worker_plugin(LoggingPlugin(c))
                client.register_worker_plugin(ProcessPoolPlugin)
            else:
                client = None
            try:
                func.main.config = config
                return func.main(**_config)
            except Exception:
                traceback_str = traceback.format_exc()
                raise Exception(
                    "Error occurred. Original traceback " "is\n%s\n" % traceback_str
                )
            finally:
                if client is not None:
                    client.close()
                logfile = os.environ.get("LOGFILE")
                with suppress(Exception):
                    path = Path(logfile)
                    shutil.copy(path, Path(func.main.config["output_dir"]) / path.name)

        PIPELINES[name] = wrapper
        return wrapper


def __getattr__(name: str):
    """Return a named plugin"""
    try:
        return PIPELINES[name]
    except KeyError:
        _import_pipelines()
        if name in PIPELINES:
            return PIPELINES[name]
        else:
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}"
            ) from None


def __dir__():
    """List available plug-ins"""
    _import_pipelines()
    return list(PIPELINES.keys())
