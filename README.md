# TinyFish Hackathon Project: ChatVerse Web Workflows

This repository is now aligned for the TinyFish $2M Pre-Accelerator Hackathon.

The core goal is to demonstrate an AI system that does real work on the live web, not just chat or summarization. This backend now includes direct TinyFish API hooks so your app can launch multi-step browser workflows and return execution results.

## Why This Fits TinyFish Hackathon

This project targets the exact judging direction:

- Real web execution through a browser agent (TinyFish API)
- Multi-step workflow orchestration (url, goal, metadata)
- Business-use automation potential (social + productivity + ops integrations already in platform)
- Deployable backend architecture (FastAPI, async services, env-based production config)

## What Was Added for TinyFish

- TinyFish API client service: `services/tinyfish_client.py`
- TinyFish router endpoints: `routers/tinyfish.py`
- Router wired into app entrypoints:
	- `app.py`
	- `app_production.py`
- TinyFish env placeholders added:
	- `.env.example`
	- `.env.template`
	- `config/settings.py`

## TinyFish Endpoints

### 1) Health check

`GET /tinyfish/health`

Returns whether TinyFish is configured and which endpoint path will be called.

### 2) Execute a web task

`POST /tinyfish/run`

Example request body:

```json
{
	"url": "https://news.ycombinator.com/jobs",
	"goal": "Extract the first 15 job postings with title, url, and posted date as JSON",
	"max_steps": 20,
	"metadata": {
		"client": "acme",
		"priority": "high"
	}
}
```

## Quick Start

1. Create env file:

```bash
cp .env.template .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.template .env
```

2. Fill required variables in `.env`:

- Supabase keys
- `TINYFISH_API_KEY`
- `TINYFISH_API_BASE_URL` (default: `https://agent.tinyfish.ai`)
- `TINYFISH_EXECUTE_PATH` (default: `/v1/automation/run-sse`)

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run backend:

```bash
python app.py
```

5. Verify TinyFish wiring:

```bash
curl http://localhost:8000/tinyfish/health
```

6. Trigger live web task:

```bash
curl -X POST http://localhost:8000/tinyfish/run \
	-H "Content-Type: application/json" \
	-d '{"url":"https://news.ycombinator.com/jobs","goal":"Extract the first 15 job postings with title, url, and posted date as JSON"}'
```

Direct TinyFish reference call format:

```bash
curl -X POST https://agent.tinyfish.ai/v1/automation/run-sse \
	-H "X-API-Key: $TINYFISH_API_KEY" \
	-H "Content-Type: application/json" \
	-d '{
		"url": "https://news.ycombinator.com/jobs",
		"goal": "Extract the first 15 job postings. For each, get the full title text, URL, and posting date as JSON array with title, url, posted"
	}'
```

## Demo Script (2-3 Minutes)

Use this flow for your hackathon video:

1. Show the business pain point (manual repetitive web workflow).
2. Show `.env` TinyFish config (hide key values).
3. Hit `POST /tinyfish/run` with a realistic task.
4. Show response and resulting actionable output in your app UI/workflow.
5. Explain measurable value: time saved, reliability, and repeatability.

## Submission Checklist

- Prototype uses TinyFish Web Agent API for real web work
- Raw 2-3 minute public demo recorded
- Demo posted on X, tagging `@Tiny_fish`
- HackerEarth submission completed
- Repository README explains setup and reproducibility

## Important Security Note

This workspace currently contains sensitive credentials in local env files. Rotate exposed keys before public submission and avoid committing `.env`.

## Next Practical Improvements

- Add task templates for high-value verticals (sales ops, recruiting ops, compliance checks)
- Store TinyFish run history and statuses in Supabase for observability
- Add retry/idempotency and webhook callbacks for longer-running workflows