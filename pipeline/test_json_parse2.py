import json, re

# 最简单的情况：行列式 和 行列式的性质3
simple_edge = '{"source": "行列式", "target": "行列式的性质3", "type": "PREREQUISITE_OF"}'
print("Test 1: simple edge JSON")
try:
    json.loads(simple_edge)
    print("  SUCCESS")
except Exception as e:
    print(f"  FAILED: {e}")

# 带 \mid 的 Formula
formula_str = '{"id": "$\\mid A (t) \\mid$", "type": "Formula"}'
print("\nTest 2: formula with backslash mid")
try:
    json.loads(formula_str)
    print("  SUCCESS")
except Exception as e:
    print(f"  FAILED: {e}")

# 完整 JSON（从报错日志取出的实际片段）
full_json = """{
  "nodes": [
    {"id": "例8", "type": "Problem"},
    {"id": "数域 K", "type": "Concept"},
    {"id": "n级矩阵", "type": "Concept"},
    {"id": "代数余子式", "type": "Concept"},
    {"id": "行列式", "type": "Concept"},
    {"id": "行列式的性质3", "type": "Theorem"},
    {"id": "$\\mid A (t) \\mid = \\mid A \\mid + t \\sum_ {i = 1} ^ {n} \\sum_ {j = 1} ^ {n} A _ {i j}$", "type": "Formula"}
  ],
  "edges": [
    {"source": "例8", "target": "数域 K", "type": "USES_CONCEPT"},
    {"source": "例8", "target": "n级矩阵", "type": "USES_CONCEPT"},
    {"source": "例8", "target": "代数余子式", "type": "USES_CONCEPT"},
    {"source": "例8", "target": "行列式", "type": "USES_CONCEPT"},
    {"source": "例8", "target": "行列式的性质3", "type": "USES_CONCEPT"},
    {"source": "行列式", "target": "行列式的性质3", "type": "PREREQUISITE_OF"},
    {"source": "行列式的性质3", "target": "$\\mid A (t) \\mid = \\mid A \\mid + t \\sum_ {i = 1} ^ {n} \\sum_ {j = 1} ^ {n} A _ {i j}$", "type": "DERIVED_FROM"},
    {"source": "例8", "target": "$\\mid A (t) \\mid = \\mid A \\mid + t \\sum_ {i = 1} ^ {n} \\sum_ {j = 1} ^ {n} A _ {i j}$", "type": "HAS_ANSWER"},
    {"source": "$\\mid A (t) \\mid = \\mid A \\mid + t \\sum_ {i = 1} ^ {n} \\sum_ {j = 1} ^ {n} A _ {i j}$", "target": "代数余子式", "type": "USES_CONCEPT"},
    {"source": "$\\mid A (t) \\mid = \\mid A \\mid + t \\sum_ {i = 1} ^ {n} \\sum_ {j = 1} ^ {n} A _ {i j}$", "target": "行列式", "type": "USES_CONCEPT"}
  ]
}"""

print("\nTest 3: full JSON with all edges")
try:
    r = json.loads(full_json)
    print(f"  SUCCESS: {len(r['nodes'])} nodes, {len(r['edges'])} edges")
except Exception as e:
    print(f"  FAILED: {e}")

# 如果上面失败了，看看是 line:col
print("\nTest 4: find the exact failure location")
try:
    json.loads(full_json)
except json.JSONDecodeError as e:
    print(f"  Error at line {e.lineno}, col {e.colno}, pos {e.pos}")
    lines = full_json.split('\n')
    print(f"  Problem line: {repr(lines[e.lineno-1])}")
    print(f"  Problem char: {repr(full_json[e.pos-5:e.pos+5])}")
