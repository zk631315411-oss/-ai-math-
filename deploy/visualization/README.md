# Manim visualization services

The web API remains outside this Compose file. Start Redis, MinIO, and the
single-concurrency Manim worker with:

```powershell
docker compose -f deploy/visualization/docker-compose.yml up --build -d
```

Use the visualization values from `.env.example` for the locally running API.
The worker mounts `data/` so it shares the current SQLite database. In cloud
deployments, replace the MinIO endpoint and credentials with a private
S3-compatible object store and keep the bucket non-public.

When Docker Desktop runs the Linux Worker against a SQLite file on a Windows
bind mount, start the API with `AI_MATH_DB_JOURNAL_MODE=DELETE`. Native Linux
deployments can keep the default `WAL` mode.

The worker accepts only versioned scene recipes produced by the API. It never
executes Python supplied by the model or the browser. Its runtime network is
internal-only and the local Compose file applies CPU, memory, PID, temporary
storage, output-size, and RQ timeout limits. Keep
`VISUALIZATION_WORKER_CONCURRENCY=1` for the initial SQLite deployment; raise it
only after moving the business database to shared storage suitable for
concurrent workers.
