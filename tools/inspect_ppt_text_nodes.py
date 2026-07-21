from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


def main() -> None:
    path = Path(sys.argv[1])
    with zipfile.ZipFile(path) as zf:
        slides = sorted(
            [name for name in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        for slide_no, name in enumerate(slides, 1):
            root = ET.fromstring(zf.read(name))
            texts = [node.text or "" for node in root.findall(".//a:t", NS)]
            print(f"--- slide {slide_no} ---")
            for idx, text in enumerate(texts):
                print(f"{idx:02d}: {text!r}")


if __name__ == "__main__":
    main()
