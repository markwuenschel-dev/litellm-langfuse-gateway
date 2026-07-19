# Kubernetes sketch (WP16) — reference only

Not a full cluster package. Use as a starting point when moving off laptop Compose. **Pinned image refs, probes, and secret references** are the important parts.

## Principles

| Rule | Detail |
| --- | --- |
| Pin digests | Same digests as `compose.yaml` / `upgrade-notes.md` |
| Secrets | External Secret / sealed secret / CSI — never in git |
| Workers | `num_workers=1` per pod; scale **replicas**, not multi-worker processes |
| Redis | Required when `replicas > 1` for shared rpm/tpm / routing state |
| Postgres | Managed or HA; required for keys/budgets/spend |
| YAML SoT | Mount `litellm-config.yaml`; `STORE_MODEL_IN_DB=False` |
| Admin UI | Private NetworkPolicy / SSO; not public by default |
| TLS | Ingress / Gateway API terminates TLS |

## Image pins (copy from compose)

```text
LiteLLM:  ghcr.io/berriai/litellm:v1.92.0@sha256:9ef6f45bc0104940571765e610c52a1d761b5ec85efcd193795281086ee61277
Postgres: postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777
Redis:    redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99
```

Bump procedure: `../upgrade-notes.md`.

## Deployment sketch (LiteLLM)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-gateway
  labels:
    app: litellm-gateway
spec:
  replicas: 1  # >1 only with Redis + shared DATABASE_URL
  selector:
    matchLabels:
      app: litellm-gateway
  template:
    metadata:
      labels:
        app: litellm-gateway
    spec:
      containers:
        - name: litellm
          image: ghcr.io/berriai/litellm:v1.92.0@sha256:9ef6f45bc0104940571765e610c52a1d761b5ec85efcd193795281086ee61277
          args: ["--config", "/app/config.yaml", "--port", "4000", "--num_workers", "1"]
          ports:
            - name: http
              containerPort: 4000
          env:
            - name: LITELLM_MODE
              value: PRODUCTION
            - name: STORE_MODEL_IN_DB
              value: "False"
            - name: LITELLM_MASTER_KEY
              valueFrom:
                secretKeyRef:
                  name: litellm-gateway-secrets
                  key: LITELLM_MASTER_KEY
            - name: LITELLM_SALT_KEY
              valueFrom:
                secretKeyRef:
                  name: litellm-gateway-secrets
                  key: LITELLM_SALT_KEY
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: litellm-gateway-secrets
                  key: DATABASE_URL
            # Provider + Langfuse keys: additional secretKeyRef entries
            # Do NOT inject REDIS_* into LiteLLM on this pin for "shared limits".
            # Redis as a sidecar/service is fine; wiring control-state requires
            # fail-closed evidence (see docs/evidence/spikes/2026-07-19-int-001-*).
          volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: litellm-config.yaml
              readOnly: true
          readinessProbe:
            httpGet:
              path: /health/readiness
              port: http
            initialDelaySeconds: 20
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health/liveliness
              port: http
            initialDelaySeconds: 40
            periodSeconds: 15
            timeoutSeconds: 5
          resources:
            requests:
              cpu: "250m"
              memory: 512Mi
            limits:
              memory: 2Gi
      volumes:
        - name: config
          configMap:
            name: litellm-gateway-config
```

## Secret inventory (names only)

| Key | Notes |
| --- | --- |
| `LITELLM_MASTER_KEY` | Admin only; rotatable |
| `LITELLM_SALT_KEY` | **Permanent** per env; offline escrow |
| `DATABASE_URL` | Postgres |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `XAI_API_KEY` | Provider |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Cloud |
| `REDIS_PASSWORD` | Only if running a Redis **service** separately; not for LiteLLM shared-limit claim |

## Smoke after deploy

```bash
kubectl port-forward svc/litellm-gateway 4000:4000
uv run llg health --path /health/readiness
# Virtual key from secret store — never master in apps
export LLG_LIVE=1 LITELLM_VIRTUAL_KEY=***
uv run llg smoke --alias llm-general
```

Deploy and live smoke remain **UNPROVEN** in the hermetic milestone until a real cluster and credentials exist.
