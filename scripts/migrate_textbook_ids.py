"""One-time migration from legacy textbook aliases to canonical IDs.

The default mode is a read-only dry run.  ``--apply`` creates a SQLite backup
before opening one immediate transaction.  Runtime code must not import the
legacy map from this module; aliases exist here only for data migration.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/learning.db"

LEGACY_TEXTBOOK_IDS = {
    "高代上-丘维声": "gaodai_shang",
    "高代下-丘维声": "gaodai_xia",
    "高数上-黄立宏": "gaoshu_shang",
    "高数下-黄立宏": "gaoshu_xia",
    "gaodai-qiuweisheng-upper": "gaodai_shang",
    "gaoshu-huang-upper-v2": "gaoshu_shang",
}

# Some context tables store the textbook in a section/sequence key rather
# than a separate textbook_id column, e.g. ``legacy-book:C03:S02``.
DIRECT_COLUMN_NAMES = {"textbook_id", "last_textbook_id", "sequence_id", "section_node_id"}
JSON_COLUMN_NAMES = {
    "context_snapshot",
    "messages_snapshot",
    "sources",
    "payload",
    "result",
    "selection_decision",
    "summary",
}


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _replace_string(value: str) -> tuple[str, int]:
    canonical = LEGACY_TEXTBOOK_IDS.get(value)
    if canonical:
        return canonical, 1
    for legacy, target in LEGACY_TEXTBOOK_IDS.items():
        prefix = f"{legacy}:"
        if value.startswith(prefix):
            return f"{target}:{value[len(prefix):]}", 1
    return value, 0


def _replace_json(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        return _replace_string(value)
    if isinstance(value, list):
        changed = 0
        result = []
        for item in value:
            migrated, count = _replace_json(item)
            result.append(migrated)
            changed += count
        return result, changed
    if isinstance(value, dict):
        changed = 0
        result = {}
        for key, item in value.items():
            migrated_key, key_count = _replace_string(key)
            migrated_item, item_count = _replace_json(item)
            if migrated_key in result and migrated_key != key:
                raise ValueError(f"JSON key collision while migrating {key!r}")
            result[migrated_key] = migrated_item
            changed += key_count + item_count
        return result, changed
    return value, 0


def _scan(conn: sqlite3.Connection) -> dict[str, Any]:
    direct = Counter()
    json_hits = Counter()
    targets: list[tuple[str, str, str]] = []
    for table in _tables(conn):
        columns = _columns(conn, table)
        for column in sorted(columns & DIRECT_COLUMN_NAMES):
            targets.append((table, column, "direct"))
            for legacy in LEGACY_TEXTBOOK_IDS:
                count = conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{column}"=?', (legacy,)
                ).fetchone()[0]
                if count:
                    direct[f"{table}.{column}:{legacy}"] += count
                prefixed = conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" LIKE ?',
                    (f"{legacy}:%",),
                ).fetchone()[0]
                if prefixed:
                    direct[f"{table}.{column}:{legacy}:prefix"] += prefixed
        for column in sorted(columns & JSON_COLUMN_NAMES):
            targets.append((table, column, "json"))
            rows = conn.execute(
                f'SELECT rowid, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'
            ).fetchall()
            for _, raw in rows:
                if not isinstance(raw, str) or not raw.strip():
                    continue
                try:
                    value = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                _, changed = _replace_json(value)
                if changed:
                    json_hits[f"{table}.{column}"] += changed
    return {
        "direct_legacy_rows": dict(sorted(direct.items())),
        "json_legacy_occurrences": dict(sorted(json_hits.items())),
        "targets": [f"{table}.{column}:{kind}" for table, column, kind in targets],
    }


def _apply(conn: sqlite3.Connection) -> dict[str, int]:
    changes = Counter()
    for table in _tables(conn):
        columns = _columns(conn, table)
        for column in sorted(columns & DIRECT_COLUMN_NAMES):
            for legacy, canonical in LEGACY_TEXTBOOK_IDS.items():
                cursor = conn.execute(
                    f'UPDATE "{table}" SET "{column}"=? WHERE "{column}"=?',
                    (canonical, legacy),
                )
                if cursor.rowcount:
                    changes[f"{table}.{column}"] += cursor.rowcount
                cursor = conn.execute(
                    f'UPDATE "{table}" SET "{column}"=? || substr("{column}", ?) '
                    f'WHERE "{column}" LIKE ?',
                    (canonical, len(legacy) + 1, f"{legacy}:%"),
                )
                if cursor.rowcount:
                    changes[f"{table}.{column}"] += cursor.rowcount
        for column in sorted(columns & JSON_COLUMN_NAMES):
            rows = conn.execute(
                f'SELECT rowid, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'
            ).fetchall()
            for rowid, raw in rows:
                if not isinstance(raw, str) or not raw.strip():
                    continue
                try:
                    value = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                migrated, changed = _replace_json(value)
                if not changed:
                    continue
                conn.execute(
                    f'UPDATE "{table}" SET "{column}"=? WHERE rowid=?',
                    (json.dumps(migrated, ensure_ascii=False, separators=(",", ":")), rowid),
                )
                changes[f"{table}.{column}"] += 1
    return dict(sorted(changes.items()))


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(source)
    backup_conn = sqlite3.connect(destination)
    try:
        source_conn.backup(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()


def migrate_database(
    database: Path,
    *,
    apply: bool = False,
    backup_path: Path | None = None,
) -> dict[str, Any]:
    database = database.resolve()
    if not database.is_file():
        raise FileNotFoundError(database)

    scan_conn = sqlite3.connect(database)
    try:
        before = _scan(scan_conn)
    finally:
        scan_conn.close()

    report: dict[str, Any] = {
        "database": str(database),
        "mode": "apply" if apply else "dry-run",
        "before": before,
        "backup": None,
        "changes": {},
    }
    if not apply:
        report["after"] = before
        report["legacy_remaining"] = sum(before["direct_legacy_rows"].values()) + sum(
            before["json_legacy_occurrences"].values()
        )
        return report

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = (backup_path or database.parent / "backups" / f"{database.stem}.pre-textbook-id-{stamp}.db").resolve()
    if backup == database:
        raise ValueError("backup path must differ from the source database")
    _backup_database(database, backup)
    report["backup"] = str(backup)

    conn = sqlite3.connect(database, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        report["changes"] = _apply(conn)
        after = _scan(conn)
        remaining = sum(after["direct_legacy_rows"].values()) + sum(
            after["json_legacy_occurrences"].values()
        )
        if remaining:
            raise RuntimeError(f"legacy textbook IDs remain after migration: {remaining}")
        conn.execute("COMMIT")
        report["after"] = after
        report["legacy_remaining"] = 0
        return report
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = migrate_database(args.database, apply=args.apply, backup_path=args.backup)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
