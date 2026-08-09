#!/bin/sh
# ---------------------------------------------------------------------------
# LexiCraft — entrypoint
#
# Aguarda o PostgreSQL (configurado via POSTGRES_HOST/POSTGRES_PORT) ficar
# pronto antes de executar o comando do serviço (web/worker/beat). Evita a
# "corrida de inicialização" do primeiro deploy, em que os containers tentam
# rodar `migrate` antes de o banco aceitar conexões, causando restart em loop
# e "failed to resolve host 'db'".
# ---------------------------------------------------------------------------
set -e

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_PASSWORD:=postgres}"
: "${POSTGRES_DB:=lexicraft}"
: "${DB_WAIT_RETRIES:=60}"
: "${DB_WAIT_DELAY:=2}"

echo "[entrypoint] Aguardando banco em ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB} ..."

i=0
while [ "$i" -lt "$DB_WAIT_RETRIES" ]; do
    i=$((i + 1))
    if python -c "
import os, sys
import psycopg
try:
    psycopg.connect(
        host=os.environ['POSTGRES_HOST'],
        port=int(os.environ['POSTGRES_PORT']),
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        dbname=os.environ['POSTGRES_DB'],
        connect_timeout=3,
    ).close()
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        echo "[entrypoint] Banco pronto."
        break
    fi
    echo "[entrypoint] Banco ainda não pronto... tentativa ${i}/${DB_WAIT_RETRIES}"
    sleep "$DB_WAIT_DELAY"
    if [ "$i" -eq "$DB_WAIT_RETRIES" ]; then
        echo "[entrypoint] ERRO: banco inalcançável após ${DB_WAIT_RETRIES} tentativas." >&2
        exit 1
    fi
done

exec "$@"
