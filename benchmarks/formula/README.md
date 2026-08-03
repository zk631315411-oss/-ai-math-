# Chinese Formula Benchmark

`dataset.py` defines a fixed suite of 325 cases: 25 cases in each of 13 formula categories. `run.py` is a direct-provider quality runner. It reuses the production prompt, uses JSON Schema first, and retries JSON Object on a 400 response:

```powershell
Copy-Item benchmarks/formula/providers.example.json benchmarks/formula/providers.local.json
python -m benchmarks.formula.run --providers benchmarks/formula/providers.local.json --profile full --output benchmark-results
```

For the 2 vCPU / 2GB Linux server, use the matrix runner instead. It starts one local `llama-server` candidate at a time, validates file SHA256, records Linux memory and swap signals, and creates `decision.md`:

```bash
node --version  # Node 22 or later
cd frontend && npm ci && cd ..
cp benchmarks/formula/candidates.server.example.json benchmarks/formula/candidates.server.json
export FORMULA_BENCHMARK_TOKEN='token for the local benchmark user'
python -m benchmarks.formula.server_matrix \
  --manifest benchmarks/formula/candidates.server.json \
  --output benchmark-results/$(date +%Y%m%d-%H%M%S)
```

The manifest's GGUF source, revision, and 64-character SHA256 placeholders must be filled with verified data. `integration.application_service` identifies the already-running application; the runner records its RSS and health latency before testing, and rejects any candidate that makes the application unavailable or restarts it. Candidate results are resumable unless `--force` is supplied. The matrix tests Qwen 0.5B, 0.6B, 0.8B, optional 0.8B Q5, and conditional 1.5B in ascending risk order.

Each line in `reviews.jsonl` is an independent human annotation for the separate production gate:

```json
{"provider":"qwen3.5-0.8b-q4_k_m","case_id":"fraction-01-01","semantic_correct":true}
```

The automated `screening_gate_passed` uses deterministic semantic comparison, KaTeX rendering, 8-second timeouts, P95 latency, peak RSS, minimum available memory, and swap activity. It remains distinct from `production_gate_passed`, which requires all 325 human annotations. `--limit` is only for local script smoke tests. Result files may contain benchmark descriptions and generated formulas, so `benchmark-results/` is ignored and must not be treated as production telemetry.
