#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "[+] Deploying Firebreak to Kubernetes"

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/elasticsearch-deployment.yaml
kubectl apply -f k8s/metasploit-deployment.yaml

echo "[*] Waiting for core services..."
kubectl wait --namespace firebreak --for=condition=available deployment/redis --timeout=180s || true
kubectl wait --namespace firebreak --for=condition=available deployment/postgres --timeout=180s || true

kubectl apply -f k8s/orchestrator-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/prometheus-deployment.yaml
kubectl apply -f k8s/grafana-deployment.yaml
kubectl apply -f k8s/ingress.yaml

if kubectl api-resources --api-group=keda.sh >/dev/null 2>&1; then
  echo "[*] KEDA detected; applying worker scaler"
  kubectl apply -f k8s/keda-worker-scaler.yaml
else
  echo "[*] KEDA not installed; skipping optional worker scaler"
fi

echo "[+] Deployment complete!"
echo "Run: kubectl get pods -n firebreak"
echo "Optional KEDA scaler: kubectl apply -f k8s/keda-worker-scaler.yaml"
