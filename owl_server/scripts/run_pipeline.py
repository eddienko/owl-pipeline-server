import asyncio
import logging
import logging.config
import signal
from argparse import Namespace

from owl_server.config import config  # noqa: F401
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
    initlog("pipeline")

    pdef = read_config(args.conf, schema_pipeline)

    try:
        start_loop(pdef)
    except:  # noqa
        logger.critical("Error running the pipeline", exc_info=True)
        raise

    logger.info("Pipeline run ended.")


def start_loop(pdef):
    loop = asyncio.get_event_loop()
    logger.info("Starting Pipeline")
    pipeline = Pipeline(pdef)

    loop.add_signal_handler(signal.SIGTERM, pipeline.close)
    loop.add_signal_handler(signal.SIGINT, pipeline.close)

    res = loop.run_until_complete(pipeline.run())
    loop.close()

    if res in ["ERROR"]:
        raise Exception()
