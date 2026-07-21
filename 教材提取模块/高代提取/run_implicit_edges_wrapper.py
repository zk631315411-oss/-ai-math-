# -*- coding: utf-8 -*-
r"""Run the shared implicit-edge generator with local env and stdlib HTTP.

This wrapper keeps the upstream generator unchanged. It only:
- loads D:\ai-math\.env into process env;
- provides a tiny requests-compatible shim when requests is unavailable;
- forwards all CLI args to 高数提取\11_generate_implicit_edges.py.
"""

from __future__ import annotations

import json
import os
import runpy
import ssl
import sys
import types
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPT = ROOT / "教材提取模块" / "高数提取" / "11_generate_implicit_edges.py"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class _Response:
    def __init__(self, status: int, body: bytes, url: str):
        self.status_code = status
        self._body = body
        self.url = url
        self.text = body.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code} for {self.url}: {self.text[:300]}")

    def json(self):
        return json.loads(self.text)


def _post(url: str, headers=None, json=None, timeout=None, verify=True):
    data = __import__("json").dumps(json or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    context = None
    if str(url).lower().startswith("https") and verify is False:
        context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            return _Response(resp.status, resp.read(), url)
    except urllib.error.HTTPError as exc:
        return _Response(exc.code, exc.read(), url)


def install_requests_shim() -> None:
    try:
        import requests  # noqa: F401
        return
    except Exception:
        pass
    urllib3 = types.SimpleNamespace(disable_warnings=lambda *args, **kwargs: None)
    sys.modules["requests"] = types.SimpleNamespace(
        post=_post,
        packages=types.SimpleNamespace(urllib3=urllib3),
    )


def main() -> None:
    load_env(ROOT / ".env")
    load_env(ROOT / "教材提取模块" / ".env")
    install_requests_shim()

    target_script = DEFAULT_SCRIPT
    forwarded = sys.argv[1:]
    if forwarded[:1] == ["--script"] and len(forwarded) >= 2:
        target_script = Path(forwarded[1])
        forwarded = forwarded[2:]

    sys.argv = [str(target_script), *forwarded]
    runpy.run_path(str(target_script), run_name="__main__")


if __name__ == "__main__":
    main()
