# Development

## Prerequisites
- Docker + Docker Compose
- An ngrok account and authtoken (already set in `.env`)

## First run
1. Copy the env template and fill in secrets (the real `.env` is gitignored):
   ```
   cp .env.example .env
   ```
   Set `NGROK_AUTHTOKEN`, and change `POSTGRES_PASSWORD` / `BASIC_AUTH_PASS` from
   the placeholder before exposing anything publicly.

2. Bring the whole stack up:
   ```
   docker compose up --build
   ```

## What runs where
| URL | What |
|---|---|
| http://localhost:8080 | The app (behind basic auth: `BASIC_AUTH_USER` / `BASIC_AUTH_PASS`) |
| http://localhost:8080/api/health | Backend health check |
| http://localhost:4040 | ngrok dashboard, shows the public HTTPS URL to share |
| http://localhost:8000 | Backend direct (host dev only) |

Get the public URL from the ngrok dashboard (http://localhost:4040) or:
```
docker compose logs ngrok
```
Share that URL plus the basic-auth username/password with your crew.

## Host dev mode (hot reload)
For fast frontend iteration, run just the data services in Docker and the Vite
dev server on the host:
```
docker compose up db backend
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to localhost:8000
```

## Notes
- M0 creates tables on startup. Alembic migrations are added in M1 as the schema
  grows.
- Images will be stored on the `images` Docker volume (used from M3 onward).
