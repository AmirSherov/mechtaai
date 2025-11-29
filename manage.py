from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config


def get_alembic_config() -> Config:
    here = Path(__file__).resolve().parent
    cfg = Config(str(here / "alembic.ini"))
    return cfg


def cmd_upgrade() -> None:
    cfg = get_alembic_config()
    command.upgrade(cfg, "head")


def cmd_downgrade(revision: str) -> None:
    cfg = get_alembic_config()
    command.downgrade(cfg, revision)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simple Alembic migration runner"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("upgrade", help="Apply all migrations (upgrade head)")

    downgrade_parser = subparsers.add_parser(
        "downgrade", help="Downgrade to a specific revision"
    )
    downgrade_parser.add_argument("revision", help="Revision id or -1, -2, ...")

    revision_parser = subparsers.add_parser(
        "revision", help="Create new alembic revision"
    )
    revision_parser.add_argument(
        "-m",
        "--message",
        required=True,
        help="Revision message",
    )
    revision_parser.add_argument(
        "--autogenerate",
        action="store_true",
        help="Populate revision with schema diff from models",
    )

    args = parser.parse_args()

    if args.command == "upgrade" or args.command is None:
        cmd_upgrade()
    elif args.command == "downgrade":
        cmd_downgrade(args.revision)
    elif args.command == "revision":
        cfg = get_alembic_config()
        command.revision(
            cfg,
            message=args.message,
            autogenerate=args.autogenerate,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
