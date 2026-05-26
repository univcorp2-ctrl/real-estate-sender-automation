from __future__ import annotations

import argparse
import json

from .config import load_config
from .orchestrator import reply_inquiry, run_daily


def main() -> None:
    parser = argparse.ArgumentParser(description="Real estate Sender automation")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("run-daily", help="Run daily/weekly property campaign pipeline")
    daily.add_argument("--dry-run", action="store_true", help="Do not call Sender for real sending")
    daily.add_argument("--verify-only", action="store_true", help="Validate and render only")

    inquiry = sub.add_parser("reply-inquiry", help="Reply to a property inquiry")
    inquiry.add_argument("--payload", required=True, help="JSON payload with email, name, property_id")

    args = parser.parse_args()
    config = load_config()
    if args.command == "run-daily":
        result = run_daily(config, dry_run=args.dry_run, verify_only=args.verify_only)
    elif args.command == "reply-inquiry":
        result = reply_inquiry(config, json.loads(args.payload))
    else:
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
