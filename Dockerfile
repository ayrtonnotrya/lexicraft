# ---------------------------------------------------------------------------
# LexiCraft — Dockerfile multi-stage
# Base: Python 3.12 slim
# ---------------------------------------------------------------------------

# ---- Etapa 1: dependências --------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copia primeiro apenas as dependências para aproveitar o cache de camadas.
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ---- Etapa 2: código da aplicação -------------------------------------------
COPY . .

# Cria diretório de estáticos coletados e do schedule do Celery Beat.
RUN mkdir -p /app/staticfiles /data

# O entrypoint aguarda o banco ficar pronto e então executa o comando do serviço.
ENTRYPOINT ["/app/entrypoint.sh"]

# Padrão (web): migrações + seed + estáticos + servidor gunicorn.
# O seeder é idempotente e roda em todo start. Os serviços worker/beat
# sobrescrevem o CMD no docker-compose.yml.
CMD ["sh", "-c", "python manage.py migrate --noinput && \
python manage.py seed_profiles && \
python manage.py collectstatic --noinput && \
gunicorn config.wsgi:application --bind 0.0.0.0:${WEB_PORT:-8000} --workers ${WEB_WORKERS:-3}"]
