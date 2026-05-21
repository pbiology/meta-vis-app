# K8s deployment against the shared KIM Keycloak

This page documents what's needed to deploy meta-vis-app to the K8s cluster
that authenticates via the **shared KIM Keycloak**, while keeping local dev
working unchanged against the bundled `meta-vis` realm on `localhost:8081`.

K8s manifests live in a separate ops repo — only the application-side bits
are documented here. Hand the Terraform snippet ([keycloak.tf.example](keycloak.tf.example))
to whoever owns the KIM realm.

## What KC config the realm owner needs to apply

See [keycloak.tf.example](keycloak.tf.example). In short:

- A public SPA client `meta-vis-frontend` (PKCE, standard flow) with redirect
  URI `https://<meta-vis-frontend-host>/auth/callback` and `web_origins = ["+"]`.
- Client roles `reader`, `writer`, `admin` on that client.
- A confidential CLI client `meta-vis-cli` with `service_accounts_enabled = true`
  and its secret stored in Vault. Its service account needs the `admin` client
  role on `meta-vis-frontend` so ingest calls have authz.
- (Verify) `meta-vis-frontend` added as a client scope on `meta-vis-cli` so
  the service-account token actually includes `resource_access["meta-vis-frontend"].roles`.

## Env vars per container

### Backend (`meta-vis-backend` deployment)

| Variable                  | Example                                                 | Notes                                                  |
| ------------------------- | ------------------------------------------------------- | ------------------------------------------------------ |
| `KEYCLOAK_ISSUER`         | `https://<kim-kc-host>/realms/<realm>`                  | Must match `iss` in tokens exactly                     |
| `KEYCLOAK_CLIENT_IDS`     | `meta-vis-frontend,meta-vis-cli`                        | `azp` allowlist                                        |
| `KEYCLOAK_ROLE_CLIENT`    | `meta-vis-frontend`                                     | Client whose roles backend reads                       |
| `KEYCLOAK_JWKS_URL`       | `http://keycloak.keycloak.svc/...` (optional)           | Override if pod can't reach public KC host             |
| `CORS_ORIGINS`            | `https://<meta-vis-frontend-host>`                      | Exact scheme + host, no trailing slash                 |
| `MONGODB_*`               | from ops repo                                           | —                                                      |
| `JWT_SECRET`              | random 32+ chars                                        | Legacy but still required by `config.py`               |

Full template: [`backend/.env.production.example`](../../backend/.env.production.example).

### Frontend (`meta-vis-frontend` deployment)

Vite bakes env vars at build time, so these are set in the **Docker build**,
not at K8s runtime:

| Variable                              | Example                                            |
| ------------------------------------- | -------------------------------------------------- |
| `VITE_OIDC_AUTHORITY`                 | `https://<kim-kc-host>/realms/<realm>`             |
| `VITE_OIDC_CLIENT_ID`                 | `meta-vis-frontend`                                |
| `VITE_OIDC_REDIRECT_URI`              | `https://<meta-vis-frontend-host>/auth/callback`   |
| `VITE_OIDC_POST_LOGOUT_REDIRECT_URI`  | `https://<meta-vis-frontend-host>/`                |
| `VITE_API_PROXY_TARGET`               | `https://<meta-vis-backend-host>`                  |

Full template: [`frontend/.env.production.example`](../../frontend/.env.production.example).

## Building the prod frontend image

Because Vite reads `.env` at build time, building the prod image means
temporarily swapping the file:

```bash
cd frontend
cp .env .env.local-dev.bak
cp .env.production.example .env             # fill in real hostnames first
docker build -t <dockerhub-user>/meta-vis-frontend:<tag> .
docker push <dockerhub-user>/meta-vis-frontend:<tag>
mv .env.local-dev.bak .env                  # restore for local dev
```

Backend has no build-time env baked in, so the same image works against any
KC instance — env vars are read at container start:

```bash
cd backend
docker build -t <dockerhub-user>/meta-vis-backend:<tag> .
docker push <dockerhub-user>/meta-vis-backend:<tag>
```

## Running ingest against the K8s instance

From a local workstation, against the deployed backend. The CLI auto-detects
client_credentials when `KEYCLOAK_CLIENT_SECRET` is set:

```bash
export KEYCLOAK_URL=https://<kim-kc-host>
export KEYCLOAK_REALM=<realm-name>
export KEYCLOAK_CLI_CLIENT_ID=meta-vis-cli
export KEYCLOAK_ROLE_CLIENT=meta-vis-frontend
export KEYCLOAK_CLIENT_SECRET=<from-vault>
export META_VIS_API=https://<meta-vis-backend-host>

python ingest.py taxprofiler --case-id ... --multiqc ... ...
```

## Gotchas to verify after first deploy

1. **`azp` value** — backend validates `azp ∈ KEYCLOAK_CLIENT_IDS` (no `aud`
   check). KIM KC should set `azp` to the client_id by default, but worth
   confirming with a real token.
2. **Service-account roles in token** — after the TF apply, inspect the CLI's
   access token and confirm it actually contains
   `resource_access["meta-vis-frontend"].roles = ["admin"]`. Without a client
   scope mapping it may not:
   ```bash
   TOKEN=$(curl -s -d "grant_type=client_credentials" \
       -d "client_id=meta-vis-cli" -d "client_secret=$KEYCLOAK_CLIENT_SECRET" \
       "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token" \
       | jq -r .access_token)
   echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq .resource_access
   ```
3. **CORS** — `CORS_ORIGINS` must list the frontend's exact public origin.
4. **JWKS reachability** — if the pod can't reach the public KC hostname,
   set `KEYCLOAK_JWKS_URL` to the in-cluster URL.

## Local dev unchanged

`make keycloak-up && make dev` continues to work against `localhost:8081`
with `dev-admin/dev-admin`. None of the local files (`backend/.env`,
`frontend/.env`, `keycloak/realm-export.json`, `docker-compose*.yml`) are
modified by this work.
