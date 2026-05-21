# Where the app runs, and how to reach it

meta-vis-app runs in two parallel deployments. They share the same code, but
each authenticates against its own Keycloak instance with different clients
and users. The local one is for developing and exercising features; the K8s
one is what clinicians and partner teams actually use.

```
                ┌───────────────────────────┐                ┌─────────────────────────────┐
                │ Local dev (your laptop)   │                │ K8s (test cluster)          │
                │                           │                │                             │
  Frontend ───▶ │ http://localhost:5173     │                │ https://metavis-frontend.   │
                │   (Vite dev server)       │                │   apps.test.kim.            │
                │                           │                │   karolinska.se             │
                │                           │                │   (OpenShift route → pod)   │
                │                           │                │                             │
  Backend  ───▶ │ http://localhost:8000     │                │ https://metavis-backend.    │
                │   (uvicorn --reload)      │                │   apps.test.kim.            │
                │                           │                │   karolinska.se             │
                │                           │                │                             │
  Auth     ───▶ │ http://localhost:8081     │                │ https://sso.test.kim.       │
                │   (local Keycloak)        │                │   karolinska.se (KIM KC)    │
                │   realm: meta-vis         │                │   realm: karolinska         │
                │                           │                │                             │
  Storage  ───▶ │ MongoDB + MinIO (Docker)  │                │ MongoDB + MinIO (in-cluster)│
                └───────────────────────────┘                └─────────────────────────────┘
```

The K8s side is deployed and managed from a separate ops repo (helm charts +
ArgoCD). This repo only produces container images and the application code.

## Local — for development

### Start the stack

```bash
# In repo root
make keycloak-up        # local Keycloak on :8081 (realm: meta-vis)

cd backend
docker compose up -d    # MongoDB + MinIO
conda activate meta-vis-app
uvicorn app.main:app --reload   # backend on :8000

cd ../frontend
npm run dev             # frontend on :5173
```

### Log in

Open <http://localhost:5173>. Click Login. Use the seeded admin account in
the local realm:

- Username: `dev-admin`
- Password: `dev-admin`

Local KC realm settings, dev user, and the two pre-configured clients
(`meta-vis-frontend`, `meta-vis-cli`) all live in
[`keycloak/realm-export.json`](../../keycloak/realm-export.json) and are
re-imported on each `make keycloak-up`.

### Ingest data

```bash
python ingest.py trana \
    --case-id my-test-case \
    --pipeline-info backend/test-data/16S_trana/pipeline_info/software_versions.yml \
    --sample "sample_id=X1 type=sample material=DNA \
abundance_path=backend/test-data/16S_trana/results/1234567890AB_downsampled.fastq_rel-abundance.tsv" \
    --password dev-admin
```

(`--password dev-admin` because local KC uses the simple password grant; the
defaults for `--url`, `--keycloak-url`, `--realm`, etc. all point at
`localhost`.)

### Reset

```bash
make keycloak-reset             # wipes the local KC volume
cd backend && docker compose down -v   # wipes Mongo + MinIO data
```

## K8s — the test deployment

### Reach it

Open <https://metavis-frontend.apps.test.kim.karolinska.se>. Click Login —
you'll be redirected to <https://sso.test.kim.karolinska.se/realms/karolinska>,
which federates out to the SITHS card IdP at `idp2-acc.ek.sll.se`. Use your
SITHS card to authenticate.

You need to be a member of whatever group/role in the karolinska realm grants
the `meta-vis-frontend` client roles (`reader`, `writer`, or `admin`). If you
get to the app but see only the login page or a 403, you don't have a role
assigned — ask the KIM Keycloak admin.

### Ingest against it

You need the CLI's client_credentials secret from Vault:
`secret/kar-app-gmck-apps/dev/meta-vis`, key `KEYCLOAK_CLI_SECRET`.

Plus the Region Stockholm root CA (the cluster's certs are signed by an
internal CA your Python doesn't trust by default — see
[Corporate-CA gotcha](#corporate-ca-gotcha) below):

```bash
# One-time: extract the corporate CA and combine with certifi's public bundle
security find-certificate -a -c "Region Stockholm" -p > /tmp/region-stockholm-ca.pem
cat "$(python -c 'import certifi; print(certifi.where())')" \
    /tmp/region-stockholm-ca.pem > /tmp/combined-ca.pem

# Add to your shell rc, or export per session
export REQUESTS_CA_BUNDLE=/tmp/combined-ca.pem
export SSL_CERT_FILE=/tmp/combined-ca.pem

# Auth config for K8s
export KEYCLOAK_URL=https://sso.test.kim.karolinska.se
export KEYCLOAK_REALM=karolinska
export KEYCLOAK_CLI_CLIENT_ID=meta-vis-cli
export KEYCLOAK_CLIENT_SECRET=$(vault kv get \
    -address=https://vault.test.kim.karolinska.se \
    -mount=secret -field=KEYCLOAK_CLI_SECRET \
    kar-app-gmck-apps/dev/meta-vis)

# Then ingest — note --url points at the K8s backend; no --password (the
# secret triggers the client_credentials grant automatically)
python ingest.py trana \
    --url https://metavis-backend.apps.test.kim.karolinska.se \
    --case-id my-test-case \
    --pipeline-info backend/test-data/16S_trana/pipeline_info/software_versions.yml \
    --sample "sample_id=X1 type=sample material=DNA \
abundance_path=backend/test-data/16S_trana/results/1234567890AB_downsampled.fastq_rel-abundance.tsv"
```

### Deploy new code to K8s

This repo builds the images; the ops repo deploys them.

1. Build & push the new images (typically to
   `artifactory.kim.karolinska.se/docker/clinicalgenomics/`). Use a fresh
   tag each time — mutable tags + `imagePullPolicy: Always` are unreliable
   for in-place updates.
2. Bump `imageTag` in the ops-repo helm values for `metavis-backend` and/or
   `metavis-frontend`, open a PR, merge.
3. ArgoCD picks up the change and rolls the pods.

The Keycloak client config (redirect URIs, client roles, CLI service
account) lives in the same ops repo's terraform under
`keycloak/karolinska/projects/gmck/clients.tf`. Any URL change (new
hostname, new prod environment) needs a TF PR there.

## When to use which

- **Building or debugging a feature** → local. Faster iteration, no auth
  hoops, you can wipe Mongo without consequences.
- **Demoing to clinicians, validating against real ingress / SITHS / TLS,
  testing the deployment path** → K8s.
- **Bug reports from clinicians** → reproduce on K8s first (to confirm),
  then debug locally if possible.

Never test destructive changes (schema migrations, data deletes) against K8s
without an explicit signal — there's no separate dev/prod split in the
cluster yet.

## Corporate-CA gotcha

The K8s cluster's TLS certs are signed by **Region Stockholm RSA CA02 L2 v3**
— a corporate CA. Your macOS keychain has it (which is why browsers trust
`*.apps.test.kim.karolinska.se` automatically), but Python's `requests` /
`urllib3` use `certifi`'s public-CA bundle, which doesn't.

Symptoms:

- `ssl.SSLCertVerificationError: ... self-signed certificate in certificate chain`
  when running `ingest.py` against K8s.
- The same error inside the backend pod when it fetches Keycloak's JWKS —
  manifests as `401 Invalid or expired token` returned to the CLI even
  though the token was valid.

Fix (laptop): extract the CA from your keychain and point Python at it via
`REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` (see ingest example above).

Fix (in-cluster pod): the helm chart mounts a `trusted-ca-bundle` ConfigMap
labeled `config.openshift.io/inject-trusted-cabundle: "true"`. OpenShift's
network operator auto-populates the bundle. The backend reads it via
`SSL_CERT_FILE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`.

## Quick reference

| What                   | Local                                          | K8s                                                        |
| ---------------------- | ---------------------------------------------- | ---------------------------------------------------------- |
| Frontend               | <http://localhost:5173>                        | <https://metavis-frontend.apps.test.kim.karolinska.se>     |
| Backend                | <http://localhost:8000>                        | <https://metavis-backend.apps.test.kim.karolinska.se>      |
| Keycloak               | <http://localhost:8081>                        | <https://sso.test.kim.karolinska.se>                       |
| Realm                  | `meta-vis`                                     | `karolinska`                                               |
| SPA client             | `meta-vis-frontend`                            | `meta-vis-frontend`                                        |
| CLI client             | `meta-vis-cli` (secret in `realm-export.json`) | `meta-vis-cli` (secret in Vault)                           |
| Login method           | dev-admin / dev-admin                          | SITHS card via `idp2-acc.ek.sll.se`                        |
| CLI auth grant         | password                                       | client_credentials                                         |
| Mongo / MinIO          | Docker on localhost                            | In-cluster services                                        |
| Deployed from          | n/a (run uvicorn / vite directly)              | ops repo helm charts, synced by ArgoCD                     |
| Code / image source    | local checkout                                 | Docker Hub / artifactory image referenced by helm `imageTag` |
