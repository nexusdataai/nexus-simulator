#!/usr/bin/env bash
# Keep the simulator UI port-forward alive across pod restarts.
set -u

export KUBECONFIG="${KUBECONFIG:-/opt/mycode/nexus/nexus-deployer/aws-login/.kube/config}"
CONTEXT="${CONTEXT:-local-cluster}"
NAMESPACE="${NAMESPACE:-simulator-local}"
SERVICE="${SERVICE:-svc/simulator-local-frontend-svc}"
LOCAL_PORT="${LOCAL_PORT:-8082}"
REMOTE_PORT="${REMOTE_PORT:-8080}"
BIND_ADDRESS="${BIND_ADDRESS:-localhost,0.0.0.0}"

while true; do
    kubectl --context "$CONTEXT" -n "$NAMESPACE" port-forward \
        --address "$BIND_ADDRESS" "$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}"
    echo "$(date -Is) port-forward exited, retrying in 3s"
    sleep 3
done
