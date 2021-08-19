"""

The database migration is based on alembic_. The usage is:

.. code-block:: text

    usage: owl-migrate [-h] [-c CONF]
                           {current,edit,show,history,revision,upgrade} ...

    Owl database migration

    optional arguments:
      -h, --help            show this help message and exit

    command:
      {current,edit,show,history,revision,upgrade}
        current             Display current revision
        edit                Edit revision
        show                Show revision
        history             Show revision history
        revision            Create a new revision file
        upgrade             Upgrade to a later version


.. _alembic: http://alembic.zzzcomputing.com/en/latest/

"""

import argparse
from datetime import datetime

from alembic import command as alembic_commands
from alembic.config import Config
from owl_server.config import config


def main():
    main_parser = argparse.ArgumentParser(description="Owl database migration")
    cmd_subparsers = main_parser.add_subparsers(title="command", dest="command")

    # current
    current_parser = cmd_subparsers.add_parser(
        "current", help="Display current revision"
    )
    current_parser.add_argument(
        "-v", "--verbose", action="store_true", help="More verbose."
    )

    # edit
    edit_parser = cmd_subparsers.add_parser("edit", help="Edit revision")
    edit_parser.add_argument("revision", type=str, help="Revision")

    # show
    show_parser = cmd_subparsers.add_parser("show", help="Show revision")
    show_parser.add_argument("revision", type=str, help="Revision")

    # history
    history_parser = cmd_subparsers.add_parser("history", help="Show revision history")
    history_parser.add_argument(
        "-v", "--verbose", action="store_true", help="More verbose."
    )

    # revision
    revision_parser = cmd_subparsers.add_parser(
        "revision", help="Create a new revision file"
    )
    revision_parser.add_argument("-m", "--message", type=str, help="Revision message.")
    revision_parser.add_argument("--id", type=str, default=None, help="Revision id.")
    revision_parser.add_argument(
        "--autogenerate", action="store_true", help="Auto generate SQL from database"
    )

    # upgrade
    upgrade_parser = cmd_subparsers.add_parser(
        "upgrade", help="Upgrade to a later version"
    )
    upgrade_parser.add_argument("revision", type=str, help="Revision")
    upgrade_parser.add_argument("--sql", action="store_true", help="SQL mode.")

    args = main_parser.parse_args()

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "owl_server:migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", config.dbi)

    if args.command == "current":
        alembic_commands.current(alembic_cfg, verbose=args.verbose)
    elif "edit" in args.command:
        alembic_commands.edit(alembic_cfg, args.revision)
    elif "show" in args.command:
        alembic_commands.show(alembic_cfg, args.revision)
    elif "history" in args.command:
        alembic_commands.history(alembic_cfg, verbose=args.verbose)
    elif "revision" in args.command:
        if args.id is None:
            rev_id = datetime.now().strftime("%Y%m%d")
        else:
            rev_id = args.id
        alembic_commands.revision(
            alembic_cfg,
            message=args.message,
            rev_id=rev_id,
            autogenerate=args.autogenerate,
        )
    elif "upgrade" in args.command:
        alembic_commands.upgrade(alembic_cfg, args.revision, sql=args.sql)
