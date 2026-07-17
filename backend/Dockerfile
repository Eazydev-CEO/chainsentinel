# ChainSentinel backend — Django + Celery
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: curl for healthchecks (psycopg[binary] needs no compiler)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
ARG REQUIREMENTS=production.txt
RUN pip install -r requirements/${REQUIREMENTS}

COPY . .

# Non-root runtime user
RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/staticfiles && chown -R app:app /app
USER app

RUN chmod +x docker/entrypoint.sh

EXPOSE 8212
ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8212", "--workers", "3", "--timeout", "60"]
