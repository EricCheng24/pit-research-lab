#!/bin/bash
# Runs only on a NEW empty official-image volume. Never performs repair.
set -eu
case "${PITLAB_TARGET:-}" in dev|test) ;; *) exit 1 ;; esac
[[ "$PITLAB_NAMESPACE" =~ ^[a-z][a-z0-9]{0,19}$ ]] || exit 1
[[ "$PITLAB_INSTANCE_ID" =~ ^[a-f0-9-]{36}$ ]] || exit 1
[[ "$PITLAB_MIGRATOR_PASSWORD" =~ ^[a-f0-9]{64}$ ]] || exit 1
[[ "$PITLAB_APP_PASSWORD" =~ ^[a-f0-9]{64}$ ]] || exit 1
[[ "$POSTGRES_DB" == "pitlab_${PITLAB_TARGET}" ]] || exit 1
[[ "$POSTGRES_USER" == "pitlab_${PITLAB_TARGET}_admin" ]] || exit 1
# psql variables use SQL literal/identifier quoting, never shell interpolation into SQL.
# Suppress error SQL/context too: bootstrap failures must not expose password-bearing DDL.
if ! psql --no-psqlrc --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=db="$POSTGRES_DB" --set=migrator="pitlab_${PITLAB_TARGET}_migrator" \
    --set=app="pitlab_${PITLAB_TARGET}_app" \
    --set=migration_password="$PITLAB_MIGRATOR_PASSWORD" --set=app_password="$PITLAB_APP_PASSWORD" \
    --set=marker="pitlab:${PITLAB_TARGET}:${PITLAB_NAMESPACE}:${PITLAB_INSTANCE_ID}" \
    >/dev/null 2>&1 <<'SQL'
BEGIN;
CREATE ROLE :"migrator" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'migration_password';
CREATE ROLE :"app" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'app_password';
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"migrator", :"app";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO :"migrator";
GRANT USAGE ON SCHEMA public TO :"app";
COMMENT ON DATABASE :"db" IS :'marker';
COMMIT;
SQL
then
    echo 'PITLab bootstrap failed; retain storage and diagnose privately. No automatic reset.' >&2
    exit 1
fi
