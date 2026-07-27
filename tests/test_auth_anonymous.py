from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.config import config
from app.db.connection import get_conn, init_db
from app.routers import auth as auth_router


class AnonymousAccessConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = f"{self.temp_dir.name}/anonymous-access.db"
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_concurrent_requests_return_one_device_account(self) -> None:
        device_id = "concurrent-device-12345678"
        barrier = threading.Barrier(2)
        call_lock = threading.Lock()
        initial_lookup_count = 0
        real_lookup = auth_router.get_user_by_device_id

        def synchronized_lookup(value: str):
            nonlocal initial_lookup_count
            existing = real_lookup(value)
            with call_lock:
                initial_lookup_count += 1
                call_number = initial_lookup_count
            if call_number <= 2:
                barrier.wait(timeout=5)
            return existing

        with (
            patch.object(auth_router, "get_user_by_device_id", side_effect=synchronized_lookup),
            patch.object(auth_router, "get_password_hash", return_value="test-hash"),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            responses = list(executor.map(auth_router.anonymous_access, [device_id, device_id]))

        self.assertEqual(responses[0].user_id, responses[1].user_id)
        self.assertEqual(responses[0].username, responses[1].username)

        conn = get_conn()
        try:
            user_count = conn.execute(
                "SELECT COUNT(1) FROM users WHERE device_id = ?", (device_id,)
            ).fetchone()[0]
            profile_count = conn.execute(
                "SELECT COUNT(1) FROM user_profiles WHERE user_id = ?",
                (responses[0].user_id,),
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(user_count, 1)
        self.assertEqual(profile_count, 1)


if __name__ == "__main__":
    unittest.main()
