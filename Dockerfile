# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_CACHE=1 PATH="/app/.venv/bin:$PATH" SQLITE_PATH=/data/washday.sqlite3 DJANGO_DEBUG=0
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir uv==0.12.23 && uv sync --locked --no-dev
COPY --chown=10001:10001 . .
RUN DJANGO_SECRET_KEY=build-only PGDATABASE=build-only PGHOST=localhost \
    PGUSER=build-only PGPASSWORD=build-only DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput && \
    useradd --uid 10001 --create-home washday && mkdir -p /data && chown washday:washday /app /data
USER washday
EXPOSE 8000
CMD ["sh", "scripts/start-web.sh"]

FROM base AS test
ENV DJANGO_DEBUG=1
USER root
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --locked
USER washday
CMD ["pytest", "--ds=config.test_settings", "-q"]

FROM base AS runtime
