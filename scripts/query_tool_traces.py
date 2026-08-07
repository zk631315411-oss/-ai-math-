"""Read-only ToolRuntime trace query."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.tool_trace_db import query_tool_traces


def main() -> None:
    parser = argparse.ArgumentParser(description="Query redacted tool call traces")
    parser.add_argument("--turn-id")
    parser.add_argument("--chat-id")
    parser.add_argument("--tool")
    parser.add_argument("--status")
    parser.add_argument("--since")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = query_tool_traces(
        turn_id=args.turn_id, chat_id=args.chat_id, tool=args.tool,
        status=args.status, since=args.since, limit=args.limit,
    )
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        return
    for row in rows:
        print(
            f"{row['created_at']} {row['status']:<9} {row['tool_name']:<28} "
            f"turn={row['turn_id']} error={row.get('error_code') or '-'}"
        )


if __name__ == "__main__":
    main()
