from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render textbook PDF pages to WebP images.")
    parser.add_argument("pdf", type=Path, help="Source PDF path")
    parser.add_argument("output_dir", type=Path, help="Output directory for page images")
    parser.add_argument("--slug", required=True, help="Stable textbook slug for manifest metadata")
    parser.add_argument("--dpi", type=int, default=120)
    parser.add_argument("--quality", type=int, default=82)
    parser.add_argument("--pdftoppm", type=Path, default=None, help="Path to pdftoppm executable")
    return parser.parse_args()


def find_pdftoppm(explicit: Path | None) -> str:
    if explicit:
        return str(explicit)
    found = shutil.which("pdftoppm")
    if found:
        return found
    texlive = Path(r"D:\tex live\texlive\2026\bin\windows\pdftoppm.exe")
    if texlive.exists():
        return str(texlive)
    raise SystemExit("pdftoppm not found. Pass --pdftoppm or install poppler/TeX Live tools.")


def convert_pngs_to_webp(tmp_dir: Path, output_dir: Path, quality: int) -> tuple[int, int, int]:
    total_bytes = 0
    width = 0
    height = 0
    count = 0

    for png_path in sorted(tmp_dir.glob("page-*.png")):
        page_number = int(png_path.stem.split("-")[-1])
        output_path = output_dir / f"page-{page_number:03d}.webp"
        with Image.open(png_path) as image:
            rgb = image.convert("RGB")
            if not width or not height:
                width, height = rgb.size
            rgb.save(output_path, "WEBP", quality=quality, method=6)
        total_bytes += output_path.stat().st_size
        count += 1

    return count, width, height, total_bytes


def main() -> None:
    args = parse_args()
    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    pdftoppm = find_pdftoppm(args.pdftoppm)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for old_page in args.output_dir.glob("page-*.webp"):
        old_page.unlink()

    with tempfile.TemporaryDirectory(prefix="textbook-pages-") as tmp:
        tmp_dir = Path(tmp)
        prefix = tmp_dir / "page"
        subprocess.run(
            [
                pdftoppm,
                "-r",
                str(args.dpi),
                "-png",
                str(args.pdf),
                str(prefix),
            ],
            check=True,
        )

        page_count, width, height, total_bytes = convert_pngs_to_webp(
            tmp_dir, args.output_dir, args.quality
        )

    manifest = {
        "slug": args.slug,
        "source": args.pdf.name,
        "pageCount": page_count,
        "dpi": args.dpi,
        "quality": args.quality,
        "width": width,
        "height": height,
        "format": "webp",
        "totalBytes": total_bytes,
        "pagePattern": "page-{page:03d}.webp",
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
