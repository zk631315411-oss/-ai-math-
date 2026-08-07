from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.migrate_textbook_ids import migrate_database


class TextbookIdMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "learning.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_database(self) -> None:
        conn = sqlite3.connect(self.database)
        try:
            conn.execute("CREATE TABLE textbook_sections (id TEXT PRIMARY KEY, textbook_id TEXT)")
            conn.execute("CREATE TABLE math_profiles (id TEXT PRIMARY KEY, last_textbook_id TEXT)")
            conn.execute("CREATE TABLE qa_turn_records (id TEXT PRIMARY KEY, textbook_id TEXT, sequence_id TEXT, section_node_id TEXT, context_snapshot TEXT)")
            conn.execute(
                "INSERT INTO textbook_sections VALUES ('s1', '高代上-丘维声')"
            )
            conn.execute(
                "INSERT INTO math_profiles VALUES ('u1', '高数下-黄立宏')"
            )
            conn.execute(
                "INSERT INTO qa_turn_records VALUES (?, ?, ?, ?, ?)",
                (
                    "t1",
                    "gaodai-qiuweisheng-upper",
                    "gaodai-qiuweisheng-upper:C03:S02",
                    "gaodai-qiuweisheng-upper:C03:S02",
                    json.dumps(
                        {
                            "textbook_id": "高代上-丘维声",
                            "section_node_id": "gaodai-qiuweisheng-upper:C03:S02",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_dry_run_is_read_only_and_apply_is_idempotent(self) -> None:
        self._create_database()
        dry_run = migrate_database(self.database)
        self.assertEqual(dry_run["mode"], "dry-run")
        self.assertGreater(dry_run["legacy_remaining"], 0)
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                conn.execute("SELECT textbook_id FROM textbook_sections").fetchone()[0],
                "高代上-丘维声",
            )
        finally:
            conn.close()

        backup = Path(self.temp_dir.name) / "backup.db"
        applied = migrate_database(self.database, apply=True, backup_path=backup)
        self.assertTrue(backup.is_file())
        self.assertEqual(applied["legacy_remaining"], 0)
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                conn.execute("SELECT textbook_id FROM textbook_sections").fetchone()[0],
                "gaodai_shang",
            )
            row = conn.execute(
                "SELECT sequence_id, section_node_id FROM qa_turn_records"
            ).fetchone()
            self.assertEqual(row, ("gaodai_shang:C03:S02", "gaodai_shang:C03:S02"))
            context = json.loads(
                conn.execute("SELECT context_snapshot FROM qa_turn_records").fetchone()[0]
            )
            self.assertEqual(context["textbook_id"], "gaodai_shang")
            self.assertEqual(context["section_node_id"], "gaodai_shang:C03:S02")
        finally:
            conn.close()

        repeated = migrate_database(
            self.database,
            apply=True,
            backup_path=Path(self.temp_dir.name) / "backup-2.db",
        )
        self.assertEqual(repeated["changes"], {})

    def test_unique_conflict_rolls_back_the_transaction(self) -> None:
        conn = sqlite3.connect(self.database)
        try:
            conn.execute(
                "CREATE TABLE cache (id INTEGER PRIMARY KEY, textbook_id TEXT UNIQUE)"
            )
            conn.execute("INSERT INTO cache(textbook_id) VALUES ('gaodai_shang')")
            conn.execute("INSERT INTO cache(textbook_id) VALUES ('高代上-丘维声')")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            migrate_database(
                self.database,
                apply=True,
                backup_path=Path(self.temp_dir.name) / "conflict-backup.db",
            )
        conn = sqlite3.connect(self.database)
        try:
            values = {row[0] for row in conn.execute("SELECT textbook_id FROM cache")}
        finally:
            conn.close()
        self.assertEqual(values, {"gaodai_shang", "高代上-丘维声"})


if __name__ == "__main__":
    unittest.main()
