#!/bin/bash
#
# Cerberus-X Metasploit RPC entrypoint.
#
# Starts a long-lived, DB-connected msfconsole that loads the MessagePack
# `msgrpc` plugin (same wire protocol as msfrpcd) after a verified
# `db_connect`. The process stays in the foreground under Docker (compose
# allocates a TTY). Database setup failures abort startup.
#
# Healthcheck coverage (see compose healthcheck):
#   - auth.login
#   - core.version
#   - db.status (requires driver=postgresql and a connected database name)
#
# Credentials / DB components come from the environment. DATABASE_URL is
# built here with URL-encoded userinfo so passwords with reserved URL
# characters do not break the connection string.
#
set -euo pipefail

: "${MSF_RPC_USER:?MSF_RPC_USER is required}"
: "${MSF_RPC_PASSWORD:?MSF_RPC_PASSWORD is required}"

# Prefer explicit MSF_DB_* components; fall back to POSTGRES_* from env_file so
# compose files do not need to interpolate passwords into URLs or YAML.
MSF_DB_USER="${MSF_DB_USER:-${POSTGRES_USER:-}}"
MSF_DB_PASSWORD="${MSF_DB_PASSWORD:-${POSTGRES_PASSWORD:-}}"
MSF_DB_NAME="${MSF_DB_NAME:-${POSTGRES_DB:-}}"
MSF_DB_HOST="${MSF_DB_HOST:-postgres}"
MSF_DB_PORT="${MSF_DB_PORT:-5432}"

: "${MSF_DB_USER:?MSF_DB_USER or POSTGRES_USER is required}"
: "${MSF_DB_PASSWORD:?MSF_DB_PASSWORD or POSTGRES_PASSWORD is required}"
: "${MSF_DB_NAME:?MSF_DB_NAME or POSTGRES_DB is required}"

export MSF_DB_USER MSF_DB_PASSWORD MSF_DB_NAME MSF_DB_HOST MSF_DB_PORT

RPC_BIND_HOST="${MSF_RPC_BIND_HOST:-0.0.0.0}"
RPC_PORT="${MSF_RPC_PORT:-55553}"
DB_HOST="${MSF_DB_HOST}"
DB_PORT="${MSF_DB_PORT}"
WAIT_RETRIES="${MSF_DB_WAIT_RETRIES:-60}"
WAIT_DELAY="${MSF_DB_WAIT_DELAY:-2}"
RC_FILE="${MSF_RC_FILE:-/tmp/msf_rpc.rc}"
DB_CONFIG_FILE="${MSF_DB_CONFIG_FILE:-/tmp/msf_database.yml}"

export MSF_RPC_BIND_HOST="${RPC_BIND_HOST}"
export MSF_RPC_PORT="${RPC_PORT}"

echo "[*] Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT} (up to $((WAIT_RETRIES * WAIT_DELAY))s)..."
attempt=0
until (exec 3<>"/dev/tcp/${DB_HOST}/${DB_PORT}") 2>/dev/null; do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge "${WAIT_RETRIES}" ]; then
    echo "[-] Timed out waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}" >&2
    exit 1
  fi
  sleep "${WAIT_DELAY}"
done
# Close the probe fd without touching stderr (a trailing `2>/dev/null` on
# `exec` permanently redirects the shell's fd 2).
exec 3<&- 3>&- || true
echo "[*] PostgreSQL is reachable"

# Build a private database YAML and resource file. Metasploit's db_connect URL
# parser does not URL-decode credentials, so a YAML file is required for
# passwords containing reserved URL characters.
echo "[*] Preparing Metasploit database config and msgrpc resource file..."
MSF_DB_PORT="${DB_PORT}" MSF_RC_FILE="${RC_FILE}" \
  MSF_DB_CONFIG_FILE="${DB_CONFIG_FILE}" \
  MSF_RPC_BIND_HOST="${RPC_BIND_HOST}" MSF_RPC_PORT="${RPC_PORT}" \
  ruby -e '
    require "yaml"

    database = {
      "adapter" => "postgresql",
      "database" => ENV.fetch("MSF_DB_NAME"),
      "username" => ENV.fetch("MSF_DB_USER"),
      "password" => ENV.fetch("MSF_DB_PASSWORD"),
      "host" => ENV.fetch("MSF_DB_HOST"),
      "port" => ENV.fetch("MSF_DB_PORT", "5432"),
      "pool" => 75,
      "timeout" => 5
    }
    File.open(ENV.fetch("MSF_DB_CONFIG_FILE"), "w", 0o600) do |file|
      file.write({ "production" => database }.to_yaml)
    end

    def msf_quote(value)
      if value.match?(/[\s"\\#]/)
        "\"#{value.gsub("\\", "\\\\\\\\").gsub("\"", "\\\\\"")}\""
      else
        value
      end
    end
    rc = <<~RC
      db_connect -y #{msf_quote(ENV.fetch("MSF_DB_CONFIG_FILE"))}
      db_status
      load msgrpc ServerHost=#{ENV.fetch("MSF_RPC_BIND_HOST")} ServerPort=#{ENV.fetch("MSF_RPC_PORT")} User=#{msf_quote(ENV.fetch("MSF_RPC_USER"))} Pass=#{msf_quote(ENV.fetch("MSF_RPC_PASSWORD"))} SSL=false
    RC
    File.open(ENV.fetch("MSF_RC_FILE"), "w", 0o600) { |f| f.write(rc) }
  '

echo "[*] Verifying database connect + schema provisioning (hard fail on error)..."
# Capture to a file (msfconsole can exit 0 even when db_connect fails).
provision_log="$(mktemp)"
set +e
./msfconsole -q -x "db_connect -y ${DB_CONFIG_FILE}; db_status; exit -y" \
  >"${provision_log}" 2>&1
provision_rc=$?
set -e
# Surface a readable subset of the provisioning log.
grep -viE 'deprecat|Gem::Platform|DidYouMean' "${provision_log}" || true

# Require an explicit connected postgresql status line. Do not treat gem paths
# like connection_adapters/postgresql as success.
if ! grep -qiE 'Connected to msf\. Connection type:[[:space:]]*postgresql' "${provision_log}"; then
  echo "[-] Database setup failed; refusing to start RPC (msfconsole_exit=${provision_rc})" >&2
  rm -f "${provision_log}"
  exit 1
fi
rm -f "${provision_log}"
echo "[*] Database schema is ready and connected"

echo "[*] Starting DB-connected msfconsole with msgrpc on ${RPC_BIND_HOST}:${RPC_PORT} (non-SSL, internal only)"
# Foreground process: compose sets tty:true so the console stays alive after
# the resource file loads msgrpc in a background thread.
exec ./msfconsole -q -r "${RC_FILE}"
