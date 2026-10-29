"""
__main__.py — Entry point for `python -m alarm_clock` and the `alarm` script.
"""

from __future__ import annotations

import sys

from .cli import build_parser, cmd_add, cmd_delete, cmd_list, cmd_next, cmd_run, cmd_snooze, cmd_toggle


_HANDLERS = {
    "add": cmd_add,
    "list": cmd_list,
    "delete": cmd_delete,
    "del": cmd_delete,
    "rm": cmd_delete,
    "toggle": cmd_toggle,
    "snooze": cmd_snooze,
    "next": cmd_next,
    "run": cmd_run,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args))


if __name__ == "__main__":
    main()
