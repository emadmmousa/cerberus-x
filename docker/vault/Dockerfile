# docker/vault/Dockerfile
FROM vault:1.15

# Copy config
COPY config/vault-config.hcl /vault/config/config.hcl

# Set environment
ENV VAULT_ADDR=http://127.0.0.1:8200
ENV VAULT_CONFIG_PATH=/vault/config

# Unseal and init script (use consul or k8s for production)
COPY init-vault.sh /usr/local/bin/init-vault.sh
RUN chmod +x /usr/local/bin/init-vault.sh

CMD ["vault", "server", "-config=/vault/config/config.hcl"]