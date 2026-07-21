from __future__ import annotations

import collections
import datetime
import json
import pathlib
import shutil


ROOT = pathlib.Path(__file__).resolve().parent
MID = ROOT / "中间产物"
SOURCES = [
    ("C07-C08", MID / "chapter_batch_c07_c08"),
    ("C09-C10_RERUN_STEP5_CLEAN", MID / "chapter_batch_c09_c10_rerun_step5_20260625"),
]
OUT = MID / "chapter_batch_c07_c10_unified_rerun_20260626"

MERGE_FILES = [
    "leaf_sections.jsonl",
    "nodes.jsonl",
    "nodes_audited.jsonl",
    "edges.jsonl",
    "edges_audited.jsonl",
    "rule_cases.jsonl",
    "rule_cases_audited.jsonl",
]

KEY_FIELDS = {
    "leaf_sections.jsonl": ["section_node_id"],
    "nodes.jsonl": ["node_id"],
    "nodes_audited.jsonl": ["node_id"],
    "edges.jsonl": ["edge_id"],
    "edges_audited.jsonl": ["edge_id"],
    "rule_cases.jsonl": ["rule_case_id", "candidate_id"],
    "rule_cases_audited.jsonl": ["rule_case_id", "candidate_id"],
}


def read_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def chapter_counts(rows: list[dict]) -> dict[str, int]:
    counts: collections.Counter[str] = collections.Counter()
    for row in rows:
        section_id = str(row.get("section_node_id") or row.get("source_code") or "")
        if ":" in section_id:
            counts[section_id.split(":")[1]] += 1
    return dict(sorted(counts.items()))


def dedupe_rows(filename: str, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    fields = KEY_FIELDS[filename]
    seen: set[tuple[str, ...]] = set()
    kept: list[dict] = []
    duplicates: list[dict] = []
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in fields)
        if not any(key):
            key = (json.dumps(row, ensure_ascii=False, sort_keys=True),)
        if key in seen:
            duplicates.append(row)
            continue
        seen.add(key)
        kept.append(row)
    return kept, duplicates


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for child_name in [
        "step6_layers",
        "step7_review",
        "step7_final",
        "step8_final_graph",
        "step9_application_validation",
    ]:
        child = OUT / child_name
        if child.exists():
            child.rename(OUT / f"{child_name}_old_{timestamp}")

    manifest: dict = {
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "output_dir": str(OUT),
        "sources": [],
        "merged_files": {},
        "notes": [
            "C07-C08 has two Step3E failures caused by empty/introductory sections absent from nodes.jsonl; accepted as non-polluting for merge input.",
            "C09-C10 source is the clean rerun from Step 5, with no failure files.",
        ],
    }

    for label, source_dir in SOURCES:
        source_info = {
            "label": label,
            "path": str(source_dir),
            "files": {},
            "failure_files": [],
        }
        for failure_file in source_dir.glob("*failures*.jsonl"):
            source_info["failure_files"].append(
                {"name": failure_file.name, "size": failure_file.stat().st_size}
            )
        for filename in MERGE_FILES:
            rows = read_jsonl(source_dir / filename)
            source_info["files"][filename] = {
                "rows": len(rows),
                "chapters": chapter_counts(rows),
            }
        manifest["sources"].append(source_info)

    for filename in MERGE_FILES:
        all_rows: list[dict] = []
        for label, source_dir in SOURCES:
            for row in read_jsonl(source_dir / filename):
                merged_row = dict(row)
                merged_row.setdefault("batch_source_label", label)
                merged_row.setdefault("batch_source_dir", str(source_dir))
                all_rows.append(merged_row)
        kept, duplicates = dedupe_rows(filename, all_rows)
        write_jsonl(OUT / filename, kept)
        manifest["merged_files"][filename] = {
            "rows": len(kept),
            "deduped": len(duplicates),
            "chapters": chapter_counts(kept),
        }

    for _, source_dir in SOURCES:
        leaf_all = source_dir / "leaf_sections_all.jsonl"
        if leaf_all.exists():
            shutil.copy2(leaf_all, OUT / "leaf_sections_all.jsonl")
            manifest["leaf_sections_all"] = {
                "source": str(leaf_all),
                "rows": len(read_jsonl(leaf_all)),
            }
            break

    for _, source_dir in SOURCES:
        tree_dir = source_dir / "tree_all"
        out_tree = OUT / "tree_all"
        if tree_dir.exists() and not out_tree.exists():
            shutil.copytree(tree_dir, out_tree)
            manifest["tree_all"] = {"source": str(tree_dir)}
            break

    (OUT / "merge_inputs_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# C07-C10 Unified Rerun Manifest",
        "",
        f"- created_at: {manifest['created_at']}",
        f"- output_dir: `{OUT}`",
        "",
    ]
    for source in manifest["sources"]:
        lines.extend(
            [
                f"## Source: {source['label']}",
                f"- path: `{source['path']}`",
                f"- failure_files: {source['failure_files'] or 'none'}",
            ]
        )
        for filename, info in source["files"].items():
            lines.append(
                f"- {filename}: {info['rows']} rows, chapters={info['chapters']}"
            )
        lines.append("")
    lines.append("## Merged Files")
    for filename, info in manifest["merged_files"].items():
        lines.append(
            f"- {filename}: {info['rows']} rows, deduped={info['deduped']}, chapters={info['chapters']}"
        )
    lines.extend(["", "## Notes"])
    lines.extend(f"- {note}" for note in manifest["notes"])
    (OUT / "merge_inputs_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(OUT)
    print(json.dumps(manifest["merged_files"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
