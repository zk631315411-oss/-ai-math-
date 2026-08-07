"""Opt-in live diagnosis smoke for an advanced algebra student."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import config
from app.services.qa.contracts import QATurnRecord
from app.services.qa.turn_store import save_turn_record


ADVANCED_RESPONSES = [
    "因为特征多项式在代数闭域上分解为一次因子，所以 Jordan 标准形可以按特征值分块；若底域不是代数闭域，则改用有理标准形描述模结构。",
    "由 Cayley-Hamilton 定理，全部特征值为零意味着特征多项式为 x^n，代入矩阵得到 A^n=0，因此矩阵必为幂零矩阵。",
    "正规矩阵可酉对角化；Schur 分解适用于任意复方阵，而正规性保证 Schur 上三角阵进一步成为对角阵。",
]


def main() -> None:
    if os.getenv("RUN_LIVE_DIAGNOSTIC_TEST") != "1":
        raise SystemExit("set RUN_LIVE_DIAGNOSTIC_TEST=1 to run the live diagnostic smoke")
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, help="Persistent isolated SQLite path")
    args = parser.parse_args()

    if args.database:
        args.database.parent.mkdir(parents=True, exist_ok=True)
        _run(args.database)
        return
    with tempfile.TemporaryDirectory(prefix="ai-math-advanced-smoke-") as directory:
        _run(Path(directory) / "advanced-smoke.db")


def _run(database: Path) -> None:
    old_db = config.DB_PATH
    old_mode = config.DIAGNOSIS_V2_MODE
    try:
        config.DB_PATH = str(database)
        config.DIAGNOSIS_V2_MODE = "full"
        from app.db.connection import get_conn, init_db
        from app.services.diagnostic_worker import run_diagnostic_batch

        init_db()
        for index, student_text in enumerate(ADVANCED_RESPONSES):
            save_turn_record(
                QATurnRecord(
                    turn_id=f"live-advanced-{index}",
                    user_id="live-advanced-student",
                    chat_id=f"live-advanced-chat-{index}",
                    marker_id="live-advanced-thread",
                    input_type="text",
                    question=student_text,
                    answer=f"AI feedback {index + 1}",
                    apprenticeship_level="fading",
                    textbook_id="高代上-丘维声",
                    sequence_id="V1-C02-S05",
                    context_snapshot={"history": []},
                ),
                write_chat_log=False,
                update_chat_history=False,
            )
        processed = asyncio.run(run_diagnostic_batch("live-advanced-student"))
        conn = get_conn()
        try:
            stages = [dict(row) for row in conn.execute(
                "SELECT concept_name,stage,confidence FROM knowledge_stages WHERE user_id=?",
                ("live-advanced-student",),
            ).fetchall()]
        finally:
            conn.close()
        print(json.dumps({"processed": processed, "database": str(database), "stages": stages}, ensure_ascii=False, indent=2))
    finally:
        config.DB_PATH = old_db
        config.DIAGNOSIS_V2_MODE = old_mode


if __name__ == "__main__":
    main()
