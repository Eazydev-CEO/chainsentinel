# Deployment

> Per project policy: **no deployment happens without the owner's explicit request.** This
> document describes *how*, not *when*.

## Production topology (docker-compose.production.yml)

```
internet ─► nginx :80/:443 ─► frontend (Next standalone :3026)
                        └───► backend (gunicorn :8212)  ─► postgres (internal only)
              celery_worker ─┘        └── redis (internal only)
              celery_beat  ──┘
```

Only nginx publishes ports. Postgres and Redis are reachable solely on the compose network.

## First deployment

```bash
# on the host
git clone <repo> chainsentinel && cd chainsentinel
cp .env.example .env
$EDITOR .env        # REQUIRED changes below
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml exec backend python manage.py createsuperuser
```

**Required `.env` changes for production**

* `DJANGO_SETTINGS_MODULE=config.settings.production`, `DJANGO_DEBUG=false`
* `DJANGO_SECRET_KEY` — long random value (startup refuses the dev placeholder)
* `DJANGO_ALLOWED_HOSTS=yourdomain.com,backend`
* `FRONTEND_URL=https://yourdomain.com`, `CSRF_TRUSTED_ORIGINS=https://yourdomain.com`
* `SECURE_COOKIES=true`
* Strong `POSTGRES_PASSWORD`
* `WEBHOOK_ENCRYPTION_KEY` — fresh Fernet key
* SMTP credentials + `PLATFORM_ALERT_EMAILS`
* Real RPC endpoints for the chains you intend to monitor

Then seed chains **without** demo data: create chains/providers via Django admin, or run
`seed_dev` only in non-production environments (it refuses when `DEBUG=false`).

## TLS

1. Obtain certificates (e.g. `certbot certonly --standalone -d yourdomain.com`).
2. Mount them (uncomment the `certs` volume in the nginx service), enable the 443 server
   block in `docker/nginx/conf.d/chainsentinel.conf`, redirect port 80.
3. `docker compose -f docker-compose.production.yml restart nginx`.
4. Keep `SECURE_COOKIES=true`; Django already honors `X-Forwarded-Proto`.

## Upgrades

```bash
git pull
docker compose -f docker-compose.production.yml up -d --build   # backend entrypoint migrates
docker compose -f docker-compose.production.yml ps              # verify healthchecks
```

Workers drain safely: `acks_late` re-queues anything interrupted; the poll lock and
idempotency keys make restarts side-effect-free.

## Backups & recovery

```bash
# nightly dump (cron on the host)
docker compose -f docker-compose.production.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backups/cs-$(date +%F).sql.gz

# restore
gunzip -c backups/cs-YYYY-MM-DD.sql.gz | docker compose -f docker-compose.production.yml \
  exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

Redis holds only cache/queues — safe to lose; deliveries in flight are re-scanned via
`next_retry_at` and polling resumes from the DB checkpoint. Also back up `.env`
(especially `WEBHOOK_ENCRYPTION_KEY` — losing it orphans webhook secrets).

## Scaling notes

* `celery_worker` scales horizontally (`--scale celery_worker=3`): per-chain locks and
  idempotency keys keep duplicates impossible. Keep **exactly one** `celery_beat`.
* gunicorn workers via the backend `CMD`; tune `--workers` to CPU.
* Move Postgres to managed hosting by changing the `POSTGRES_*` vars and deleting the
  service — nothing else changes.

## Health & monitoring

* `GET /healthz/` (backend, used by compose healthchecks and nginx).
* Django admin → Worker job logs / System errors / Reorg incidents / Provider health.
* `docker compose … logs -f celery_worker` for engine activity.
