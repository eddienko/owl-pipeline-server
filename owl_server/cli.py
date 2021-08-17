import io
import os
import sys
from argparse import ArgumentParser, FileType, Namespace
from typing import List

from owl_server.log import initlog
from owl_server.scripts import run_api, run_pipeline, run_scheduler


def parse_args(input: List[str]) -> Namespace:
    """Parse command line arguments.

    Parameters
    ----------
    input
        list of command line arguments

    Returns
    -------
    parsed arguments
    """
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    # Scheduler
    scheduler = subparsers.add_parser("scheduler")
    scheduler.add_argument("--conf", required=False, type=FileType("r"))
    scheduler.set_defaults(func=run_scheduler)

    # Run the API
    api = subparsers.add_parser("api")
    api.add_argument("--conf", required=False, type=FileType("r"))
    api.set_defaults(func=run_api)

    # Run a pipeline
    run = subparsers.add_parser("pipeline")
    run.add_argument(
        "conf", nargs="?", type=FileType("r"), default=io.StringIO(os.getenv("PIPEDEF"))
    )
    run.set_defaults(func=run_pipeline)

    args = parser.parse_args(input)
    if not hasattr(args, "func"):
        parser.print_help()

    return args


def main():
    """Main entry point for owl.

    Invoke the command line help with::

        $ owl-server --help

    """
    initlog("cli")

    args = parse_args(sys.argv[1:])

    if hasattr(args, "func"):
        args.func(args)
