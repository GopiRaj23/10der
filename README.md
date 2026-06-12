# 10der

**TenderRadar** — Indian Government Tender Aggregator SaaS.

The complete application (FastAPI backend, React frontend, Docker Compose stack,
docs) lives in the [`dev/`](dev/) subfolder.

```bash
git clone <this-repo> && cd 10der/dev
cp .env.example .env
docker compose up --build        # → http://localhost
```

Full setup instructions, architecture and demo credentials: [`dev/README.md`](dev/README.md)

> ⚠️ This app aggregates publicly available tender information.
> Always verify on the official portal before bidding.
