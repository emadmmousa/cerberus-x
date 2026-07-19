#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

NAMESPACE="cerberus-x"
RELEASE_NAME="cerberus"

if ! command -v helm >/dev/null 2>&1; then
  echo "[-] helm is not installed. Install with: brew install helm"
  echo "[*] Falling back to raw manifests: ./k8s/deploy.sh"
  exec "${ROOT_DIR}/k8s/deploy.sh"
fi

echo "[+] Deploying Cerberus-X via Helm"

kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install "${RELEASE_NAME}" ./helm/cerberus \
  --namespace "${NAMESPACE}" \
  --set redis.password="$(openssl rand -base64 16)" \
  --set postgres.password="$(openssl rand -base64 16)" \
  --set metasploit.rpcPassword="$(openssl rand -base64 16)" \
  --set ingress.host=cerberus.yourdomain.com

echo "[+] Helm deployment complete!"
echo "Note: chart currently ships orchestrator template only; use ./k8s/deploy.sh for the full stack."
echo "Run: helm list -n ${NAMESPACE}"
