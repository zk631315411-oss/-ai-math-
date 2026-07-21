import json, re

raw = """{
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

print("Test 1: raw json.loads()")
try:
    r = json.loads(raw)
    print(f"  SUCCESS: {len(r['nodes'])} nodes, {len(r['edges'])} edges")
except Exception as e:
    print(f"  FAILED: {e}")

print()
print("Test 2: various leading noise")
for prefix in ["", "\n", "  \n", "json\n", "```\n"]:
    try:
        json.loads(prefix + raw)
        print(f"  prefix={repr(prefix)}: SUCCESS")
    except Exception as e:
        print(f"  prefix={repr(prefix)}: FAILED - {e}")

print()
print("Test 3: what's really failing? Let's check the exact error message format")
from langchain_core.output_parsers import JsonOutputParser
parser = JsonOutputParser()
try:
    parser.parse(raw)
except Exception as e:
    print(f"JsonOutputParser error type: {type(e).__name__}")
    print(f"JsonOutputParser error msg: {str(e)[:200]}")
