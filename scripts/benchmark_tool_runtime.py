"""Run the 10 text + 10 screenshot latency benchmark against the local SSE API."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import statistics
import time

import httpx


TEXT_CASES = [
    "画出 y=sin(x) 并说明周期与零点。",
    "解释割线趋近切线如何得到导数。",
    "用黎曼和解释定积分，并展示细分过程。",
    "展示矩阵 [[1,1],[0,1]] 对网格和向量的变换。",
    "查询教材中极限的严格定义。",
    "查询知识图谱中特征值的前置概念。",
    "核对多项式 x^2-1 的因式分解。",
    "比较 y=x^2 与 y=(x-1)^2+2 的图像变化。",
    "画参数曲线 x=cos(t), y=sin(t)。",
    "展示向量 (1,2) 与 (2,-1) 并解释点积。",
]

SCREENSHOT_QUESTIONS = [
    "识别并解答截图中的函数题。",
    "识别截图公式并说明求导步骤。",
    "分析截图中的极限题。",
    "解释截图中的定积分示意图。",
    "识别并验证截图中的矩阵计算。",
    "分析截图中的特征值问题。",
    "解释截图中的向量关系。",
    "识别截图中的参数曲线并作图。",
    "分析截图中的证明题。",
    "识别题目条件并给出完整解答。",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--screenshot-dir", type=Path, help="Directory containing 01.png through 10.png")
    parser.add_argument("--user-id", default="tool-runtime-benchmark")
    parser.add_argument("--textbook-id", default="高代上-丘维声")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cases = [("text", question, None) for question in TEXT_CASES]
    if args.screenshot_dir:
        for index, question in enumerate(SCREENSHOT_QUESTIONS, 1):
            path = args.screenshot_dir / f"{index:02d}.png"
            if not path.exists():
                raise SystemExit(f"missing screenshot fixture: {path}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            cases.append(("screenshot", question, f"data:image/png;base64,{encoded}"))

    results = []
    with httpx.Client(timeout=None) as client:
        for input_type, question, image_data in cases:
            payload = {
                "user_id": args.user_id,
                "question": question,
                "textbook_id": args.textbook_id,
                "image_data": image_data,
            }
            started = time.perf_counter()
            done = {}
            tool_calls = 0
            with client.stream("POST", f"{args.base_url}/api/qa/solve-stream", json=payload) as response:
                response.raise_for_status()
                event_name = ""
                for line in response.iter_lines():
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if event_name == "tool_call":
                            tool_calls += 1
                        elif event_name == "done":
                            done = data
            results.append({
                "input_type": input_type,
                "question": question,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "tool_calls": tool_calls,
                "degraded": bool(done.get("degraded")),
                "tool_stats": done.get("tool_stats") or {},
            })

    latencies = [row["latency_ms"] for row in results]
    report = {
        "count": len(results),
        "p50_ms": round(statistics.median(latencies)),
        "p95_ms": round(_percentile(latencies, 0.95)),
        "max_ms": max(latencies),
        "degradation_rate": sum(row["degraded"] for row in results) / len(results),
        "results": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")


def _percentile(values: list[int], percentile: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


if __name__ == "__main__":
    main()
