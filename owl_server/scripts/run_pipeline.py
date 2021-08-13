import asyncio
import logging
import logging.config
import os
import signal
from argparse import Namespace
from pathlib import Path

from owl_server.config import config
from owl_server.daemon import Pipeline
from owl_server.log import initlog
from owl_server.schema import schema_pipeline
from owl_server.utils import read_config

logger = logging.getLogger("owl.cli")


def run_pipeline(args: Namespace) -> None:
    """Run scheduler.

    Parameters
    ----------
    arg
        Argparse namespace containing command line flags.
    """
    pdef = read_config(args.conf, schema_pipeline)

    try:
        start_loop(pdef)
    except:  # noqa
        logger.critical("Error starting the pipeline", exc_info=True)


def start_loop(pdef):
    loop = asyncio.get_event_loop()
    logger.info("Starting Pipeline")
    pipeline = Pipeline(pdef)

    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    loop.add_signal_handler(signal.SIGINT, loop.stop)

    loop.run_forever()
    loop.run_until_complete(pipeline.stop())

    loop.close()
