# Deployment

Development runs on this machine via `docker-compose.yml` (see `DEVELOPMENT.md`),
exposed to a phone/crew through the ngrok container. This file covers a real
production deployment when you outgrow ngrok.

## What changes from dev to prod
- No source bind-mounts and no `--reload` (code is baked into the images).
- `restart: unless-stopped` on every service.
- Frontend on host port 80 (put TLS in front of it).
- No ngrok, use a real domain.
- Uvicorn runs with workers.

## Steps (single small VPS)
1. Install Docker + Docker Compose on the host.
2. Copy the repo across (or `git clone`).
3. Create `.env.prod` from `.env.example` and set **strong** values for
   `POSTGRES_PASSWORD` and `BASIC_AUTH_PASS`. Point `DATABASE_URL` at the same
   Postgres credentials.
4. Bring it up:
   ```
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
   ```
5. Put TLS in front. Easiest is a reverse proxy such as Caddy (automatic Let's
   Encrypt) proxying `:443` to the frontend container's `:80`, or use your
   platform's load balancer. Never serve basic-auth credentials over plain HTTP.

## Platform alternatives
The same Compose stack runs on Fly.io, Railway, or Render with a managed Postgres.
Swap the `db` service for the managed instance and set `DATABASE_URL` accordingly;
mount a persistent volume for `IMAGE_DIR` (stone images).

## Backups
- Postgres: `docker compose exec db pg_dump -U <user> <db>` on a schedule.
- Images: back up the `images` volume (stone crops + warped source photos).

## Data growth
Stone crops and warped source photos accumulate on the `images` volume. At ~150
stones per wall this is small (a few MB), but for many projects move image storage
to object storage (S3-compatible) and serve via a CDN.

## Notes
- Auth is currently a single shared basic-auth login (fine for a small crew).
  Real per-user accounts are a future step if the audience grows.
- Schema is created on startup via SQLAlchemy `create_all`. Introduce Alembic
  before the first backwards-incompatible schema change in production.
