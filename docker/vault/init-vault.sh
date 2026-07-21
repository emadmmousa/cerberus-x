#!/bin/bash
sleep 5
vault login ${VAULT_TOKEN}

vault secrets enable kv-v2

vault kv put kv-v2/database/postgres username=firebreak password=${DB_PASS}
vault kv put kv-v2/redis password=${REDIS_PASS}
vault kv put kv-v2/api/keys google=${GOOGLE_CLIENT_ID} github=${GITHUB_CLIENT_ID}

vault secrets enable database
vault write database/config/postgres-db \
    plugin_name=postgresql-database-plugin \
    allowed_roles="postgres-role" \
    connection_url="postgresql://{{username}}:{{password}}@postgres:5432/firebreak" \
    username="firebreak" \
    password="${DB_PASS}"

vault write database/roles/postgres-role \
    db_name=postgres-db \
    creation_statements="CREATE USER \"{{name}}\" WITH PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="24h"

echo "Vault initialized successfully"