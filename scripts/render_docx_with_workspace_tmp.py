import os
import runpy
import sys
import tempfile
from pathlib import Path


ROOT = Path(r"D:\ai-math")
tmp_dir = ROOT / ".tmp" / "docx_render"
tmp_dir.mkdir(parents=True, exist_ok=True)

os.environ["TEMP"] = str(tmp_dir)
os.environ["TMP"] = str(tmp_dir)
os.environ["TMPDIR"] = str(tmp_dir)
tempfile.tempdir = str(tmp_dir)

render_script = Path(
    r"C:\Users\hp\.codex\plugins\cache\openai-primary-runtime\documents\26.515.10909\skills\documents\render_docx.py"
)

sys.argv = [str(render_script), *sys.argv[1:]]
runpy.run_path(str(render_script), run_name="__main__")
