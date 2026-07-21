import json

# Test 1: Does the JSON start with { ?
test_starts = [
    '{"nodes',
    ' { "nodes',  # leading space
    '\n{"nodes',  # leading newline
    '\ufeff{"nodes',  # BOM
]
for t in test_starts:
    try:
        json.loads(t + ']}')
        print(f"{repr(t):20s}: SUCCESS")
    except Exception as e:
        print(f"{repr(t):20s}: FAILED - {e}")

print()

# Test 2: The ACTUAL problem - LaTeX \mid in a JSON string value
# In Python string: "\\mid" = single backslash + m (invalid JSON escape)
test_latex = '{"id": "$\\mid A$"}'  # \\mid in Python = \mid actual = INVALID
print(f"Test string: {repr(test_latex)}")
print(f"  Contains: {[c for c in test_latex[7:12]]}")
try:
    json.loads(test_latex)
    print("  Result: SUCCESS")
except Exception as e:
    print(f"  Result: FAILED - {e}")

# Test 3: Fix with double escape
test_latex_fixed = '{"id": "$\\\\mid A$"}'  # \\\\ = two backslashes = valid JSON escape
print(f"\nFixed string: {repr(test_latex_fixed)}")
try:
    result = json.loads(test_latex_fixed)
    print(f"  Result: SUCCESS - {result}")
except Exception as e:
    print(f"  Result: FAILED - {e}")

print()

# Test 4: What does LLM actually return for \mid?
# If LLM returns $\mid$ (single backslash), JSON parse fails
# If LLM returns $\\mid$ (double backslash), JSON parse succeeds
llm_single = r'{"id": "$\mid$"}'  # single backslash
llm_double = r'{"id": "$\\mid$"}'  # double backslash
for label, s in [("single \\", llm_single), ("double \\\\", llm_double)]:
    try:
        json.loads(s)
        print(f"{label}: SUCCESS")
    except Exception as e:
        print(f"{label}: FAILED - {e}")
