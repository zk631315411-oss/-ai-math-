"""Print anonymous outcome metrics for competition-demo practice sessions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.connection import get_conn


def collect_metrics() -> dict:
    conn = get_conn()
    try:
        sessions = conn.execute(
            """SELECT COUNT(DISTINCT s.id) AS started,
                      COUNT(DISTINCT CASE WHEN s.status IN ('completed','inconclusive') THEN s.id END) AS finished
               FROM practice_sessions s
               JOIN practice_draft_items d ON d.draft_id=s.draft_id
               WHERE d.item_id LIKE 'mvp-%'"""
        ).fetchone()
        verdict_rows = conn.execute(
            """SELECT p.verdict,COUNT(*) AS n
               FROM practice_attempts p JOIN exercise_items i ON i.id=p.item_id
               WHERE i.id LIKE 'mvp-%' GROUP BY p.verdict"""
        ).fetchall()
        hint_row = conn.execute(
            """SELECT COUNT(*) AS hint_events,
                      COUNT(DISTINCT h.session_id) AS sessions_with_hints
               FROM practice_hint_events h JOIN exercise_items i ON i.id=h.item_id
               WHERE i.id LIKE 'mvp-%'"""
        ).fetchone()
        repeated = conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT p.session_id
                   FROM practice_attempts p JOIN exercise_items i ON i.id=p.item_id
                   WHERE i.id LIKE 'mvp-%' AND p.verdict='incorrect'
                   GROUP BY p.session_id HAVING COUNT(*)>=2
               )"""
        ).fetchone()[0]
        independent_correct = conn.execute(
            """SELECT COUNT(*) FROM practice_attempts p JOIN exercise_items i ON i.id=p.item_id
               WHERE i.id LIKE 'mvp-%' AND p.verdict='correct' AND p.hint_level=0"""
        ).fetchone()[0]
        started = int(sessions["started"] or 0)
        finished = int(sessions["finished"] or 0)
        return {
            "sessions_started": started,
            "sessions_finished": finished,
            "completion_rate": round(finished / started, 3) if started else 0.0,
            "verdict_counts": {row["verdict"]: int(row["n"]) for row in verdict_rows},
            "hint_events": int(hint_row["hint_events"] or 0),
            "sessions_with_hints": int(hint_row["sessions_with_hints"] or 0),
            "independent_correct_attempts": int(independent_correct),
            "sessions_with_repeated_errors": int(repeated),
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = collect_metrics()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
