import asyncio
import logging
import logging.config
import signal
from argparse import Namespace
from pathlib import Path

from owl_server.config import config  # noqa: F401
from owl_server.daemon import Scheduler
from owl_server.log import initlog

logger = logging.getLogger("owl.cli")


def run_scheduler(args: Namespace) -> None:
    """Run scheduler.

    Parameters
    ----------
    arg
        Argparse namespace containing command line flags.
    """
    initlog("scheduler")

    for d in ["conf", "logs"]:
        path = Path("/var/run/owl") / d
        path.mkdir(parents=True, exist_ok=True)

    try:
        start_loop()
    except:  # noqa
        logger.critical("Error starting the scheduler", exc_info=True)


def start_loop():
    loop = asyncio.get_event_loop()
    logger.info("Starting Owl Scheduler")
    scheduler = Scheduler()

    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    loop.add_signal_handler(signal.SIGINT, loop.stop)

    loop.run_forever()
    loop.run_until_complete(scheduler.stop())

    loop.close()
