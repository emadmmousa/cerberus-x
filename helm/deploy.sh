#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

NAMESPACE="firebreak"
RELEASE_NAME="firebreak"

if ! command -v helm >/dev/null 2>&1; then
  echo "[-] helm is not installed. Install with: brew install helm"
  echo "[*] Falling back to raw manifests: ./k8s/deploy.sh"
  exec "${ROOT_DIR}/k8s/deploy.sh"
fi

echo "[+] Deploying Firebreak via Helm"

kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install "${RELEASE_NAME}" ./helm/firebreak \
  --namespace "${NAMESPACE}" \
  --set redis.password="$(openssl rand -base64 16)" \
  --set metasploit.rpcPassword="$(openssl rand -base64 16)" \
  --set ingress.host=app.firebreak.com

echo "[+] Helm deployment complete!"
echo "Chart includes orchestrator, worker, Redis, Elasticsearch, Metasploit, output PVC."
echo "See helm/firebreak/README.md for firebreak.* values (Auth0, cost route, edition)."
echo "Run: helm list -n ${NAMESPACE}"
