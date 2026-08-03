# Formula Conversion Deployment

Formula conversion is attempted in this order:

1. Local OpenAI-compatible `llama-server`, if configured.
2. Cloudflare Workers AI Qwen, if configured.
3. The project's existing profile model.

## 2GB server screening

On a 2 vCPU / 2GB CPU-only server, do not enable a local model before running the automated screening matrix. Copy the candidate manifest outside Git, replace every source/revision/SHA256 placeholder with a verified GGUF artifact, and provide a short-lived benchmark token only in the shell environment:

```bash
node --version  # Node 22 or later
cd frontend && npm ci && cd ..
cp benchmarks/formula/candidates.server.example.json benchmarks/formula/candidates.server.json
export FORMULA_BENCHMARK_TOKEN='token for the local benchmark user'
python -m benchmarks.formula.server_matrix \
  --manifest benchmarks/formula/candidates.server.json \
  --output benchmark-results/$(date +%Y%m%d-%H%M%S)
```

The runner is Linux-only and performs three cold starts, the 39-case smoke set, the 325-case quality set, a 65-case determinism check, two-request bursts, and 26 authenticated API checks. It writes `decision.md`; only a `PASS` recommendation may be considered for local gray testing. A screening pass is not a production pass because it has no human semantic review.

The runner rejects a model when its source metadata or SHA256 is missing, its process exceeds the 2GB-server resource limits, the already-running application fails its health checks, the API integration is not configured, or the model fails the quality/latency gates. If every candidate fails, leave Cloudflare as the primary provider.

## Local candidate deployment

Build the latest stable llama.cpp release on the target Alibaba Cloud server. Place the GGUF outside the repository, install `deploy/formula-llama/ai-math-formula.service` as `/etc/systemd/system/ai-math-formula.service`, and place its environment file at `/etc/ai-math/formula-llama.env`.

The supplied unit binds `llama-server` to `127.0.0.1`; do not expose port 8080 publicly. Configure the API process with:

```dotenv
FORMULA_LOCAL_API_BASE=http://127.0.0.1:8080/v1
FORMULA_LOCAL_API_KEY=local
FORMULA_LOCAL_MODEL=formula-model
```

Configure `/etc/ai-math/formula-llama.env` for the systemd unit with:

```dotenv
FORMULA_GGUF_PATH=/opt/ai-math/models/verified-model.gguf
FORMULA_CONTEXT_SIZE=1024
FORMULA_THREADS=2
```

Then enable the unit:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-math-formula.service
curl http://127.0.0.1:8080/health
```

Run the matrix on that same server before enabling the service. Do not mark the result as production-ready unless the report has all 325 human reviews and `production_gate_passed` is `true`.

## Cloudflare fallback

```dotenv
FORMULA_CLOUDFLARE_ACCOUNT_ID=...
FORMULA_CLOUDFLARE_API_TOKEN=...
FORMULA_CLOUDFLARE_MODEL=@cf/qwen/qwen3-30b-a3b-fp8
```

Use an API token scoped only to Workers AI. Secrets belong in the deployment environment, never in provider JSON or Git.

## Existing model fallback

`FORMULA_EXISTING_*` inherits `PROFILE_LLM_*` when omitted or empty. Set the three variables separately only when formula conversion needs a different OpenAI-compatible endpoint, key, or model.

Production logs contain provider name, latency, status, and error type only. They do not contain descriptions, generated formulas, or user corrections.
