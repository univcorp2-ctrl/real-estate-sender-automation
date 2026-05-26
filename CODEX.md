# CODEX

## Project intent

Build a safe, auditable automation pipeline for recurring real-estate property emails using Google Drive, Sender.net, Cloudflare Worker/D1, and GitHub Actions.

## Constraints

- Never commit real API tokens or service account JSON.
- Prefer Cloudflare Worker Secrets for Sender API tokens.
- Keep Sender delivery idempotent through D1 `sent_log`.
- Keep GitHub Actions concurrency enabled.
- Validate data before rendering and validate rendered output before sending.
- Default local runs to dry-run.

## Common commands

```bash
pip install -r requirements.txt
pytest -q
ruff check .
python -m property_mailer run-daily --dry-run
cd worker && npm install && npm run typecheck
```

## Important files

- `property_mailer/orchestrator.py`: main pipeline
- `property_mailer/validation.py`: double-check rules
- `worker/src/index.ts`: Cloudflare Secret/D1/Sender gateway
- `.github/workflows/property-mailer.yml`: production schedule
- `docs/setup.md`: initial setup
