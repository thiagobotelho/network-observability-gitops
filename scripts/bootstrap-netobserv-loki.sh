#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

OC_BIN="${OC_BIN:-oc}"
if ! command -v "$OC_BIN" >/dev/null 2>&1 && [ -x "$HOME/.local/bin/oc" ]; then
  OC_BIN="$HOME/.local/bin/oc"
fi

NETOBSERV_NAMESPACE="${NETOBSERV_NAMESPACE:-netobserv}"
NETOBSERV_LOKI_SECRET="${NETOBSERV_LOKI_SECRET:-netobserv-loki-s3}"
NETOBSERV_LOKI_BUCKET="${NETOBSERV_LOKI_BUCKET:-netobserv}"
MINIO_NAMESPACE="${MINIO_NAMESPACE:-openshift-logging}"
MINIO_SECRET_NAME="${MINIO_SECRET_NAME:-minio-credentials}"
MINIO_SERVICE_HOST="${MINIO_SERVICE_HOST:-minio.openshift-logging.svc}"
MINIO_SERVICE_PORT="${MINIO_SERVICE_PORT:-9000}"
MINIO_REGION="${MINIO_REGION:-us-east-1}"
MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z}"

require_secret_key() {
  local namespace="$1"
  local secret="$2"
  local key="$3"
  "$OC_BIN" -n "$namespace" get secret "$secret" -o "jsonpath={.data.$key}" | base64 -d
}

echo "[INFO] Validando acesso ao cluster..."
"$OC_BIN" whoami >/dev/null

echo "[INFO] Garantindo namespace ${NETOBSERV_NAMESPACE}..."
"$OC_BIN" create namespace "$NETOBSERV_NAMESPACE" --dry-run=client -o yaml | "$OC_BIN" apply -f -

echo "[INFO] Lendo credenciais do MinIO local em ${MINIO_NAMESPACE}/${MINIO_SECRET_NAME}..."
MINIO_ROOT_USER="$(require_secret_key "$MINIO_NAMESPACE" "$MINIO_SECRET_NAME" "root-user")"
MINIO_ROOT_PASSWORD="$(require_secret_key "$MINIO_NAMESPACE" "$MINIO_SECRET_NAME" "root-password")"

echo "[INFO] Criando/atualizando Secret ${NETOBSERV_NAMESPACE}/${NETOBSERV_LOKI_SECRET}..."
"$OC_BIN" -n "$NETOBSERV_NAMESPACE" create secret generic "$NETOBSERV_LOKI_SECRET" \
  --from-literal=access_key_id="$MINIO_ROOT_USER" \
  --from-literal=access_key_secret="$MINIO_ROOT_PASSWORD" \
  --from-literal=bucketnames="$NETOBSERV_LOKI_BUCKET" \
  --from-literal=endpoint="http://${MINIO_SERVICE_HOST}:${MINIO_SERVICE_PORT}" \
  --from-literal=region="$MINIO_REGION" \
  --dry-run=client -o yaml | "$OC_BIN" apply -f -

echo "[INFO] Garantindo bucket ${NETOBSERV_LOKI_BUCKET} no MinIO local..."
cat <<YAML | "$OC_BIN" apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: netobserv-create-loki-bucket
  namespace: ${NETOBSERV_NAMESPACE}
  annotations:
    argocd.argoproj.io/compare-options: IgnoreExtraneous
spec:
  backoffLimit: 6
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: mc
          image: ${MINIO_MC_IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: MINIO_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: ${NETOBSERV_LOKI_SECRET}
                  key: access_key_id
            - name: MINIO_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: ${NETOBSERV_LOKI_SECRET}
                  key: access_key_secret
            - name: MINIO_ENDPOINT
              value: http://${MINIO_SERVICE_HOST}:${MINIO_SERVICE_PORT}
            - name: NETOBSERV_LOKI_BUCKET
              value: ${NETOBSERV_LOKI_BUCKET}
            - name: HOME
              value: /tmp
            - name: MC_CONFIG_DIR
              value: /tmp/.mc
          command: ["/bin/sh", "-lc"]
          args:
            - |
              set -eu
              until mc alias set local "\$MINIO_ENDPOINT" "\$MINIO_ACCESS_KEY" "\$MINIO_SECRET_KEY"; do
                echo "waiting minio..."
                sleep 3
              done
              mc mb -p "local/\$NETOBSERV_LOKI_BUCKET" || true
              mc ls "local/\$NETOBSERV_LOKI_BUCKET" >/dev/null
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            runAsNonRoot: true
            seccompProfile:
              type: RuntimeDefault
YAML

"$OC_BIN" -n "$NETOBSERV_NAMESPACE" wait --for=condition=complete job/netobserv-create-loki-bucket --timeout=5m

echo "[INFO] Bootstrap do Loki dedicado do NetObserv concluído."
