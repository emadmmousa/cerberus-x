# Official multi-architecture Metasploit Framework image (amd64 + arm64).
FROM metasploitframework/metasploit-framework:latest

# Foreground entrypoint: wait for PostgreSQL, verify db_connect, then run a
# long-lived msfconsole that loads MessagePack msgrpc on the internal network.
# Build context must be the repository root (COPY path below).
COPY docker/metasploit-entrypoint.sh /usr/local/bin/metasploit-entrypoint.sh
RUN chmod +x /usr/local/bin/metasploit-entrypoint.sh

# Run as root so the entrypoint owns the process directly (MSF_UID=0 path of
# the base image), keeping signal handling and the foreground console simple.
ENV MSF_UID=0

EXPOSE 55553

ENTRYPOINT ["/usr/local/bin/metasploit-entrypoint.sh"]
