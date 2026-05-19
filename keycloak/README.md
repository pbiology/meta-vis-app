# Local Keycloak for meta-vis-app

This directory contains the local Keycloak setup used during development. It is
**dev-only** — credentials and client secrets here must never be reused in any
deployed environment.

## Quick start

```bash
make keycloak-up       # start Keycloak (detached)
make keycloak-logs     # tail logs (watch for "Imported realm meta-vis")
make keycloak-down     # stop, keep data
make keycloak-reset    # stop and wipe the volume (forces re-import)
```

## Endpoints

| What                | URL                                                                  |
| ------------------- | -------------------------------------------------------------------- |
| Admin console       | http://localhost:8081                                                |
| OIDC discovery      | http://localhost:8081/realms/meta-vis/.well-known/openid-configuration |
| Realm account page  | http://localhost:8081/realms/meta-vis/account                        |

## Credentials (dev only)

| Role                  | Username     | Password     |
| --------------------- | ------------ | ------------ |
| Master admin (KC)     | `admin`      | `admin`      |
| `meta-vis` realm user | `dev-admin`  | `dev-admin`  |

The `dev-admin` user has the `admin` realm role assigned.

## Realm contents

Defined in [`realm-export.json`](./realm-export.json):

- Realm: `meta-vis`
- Realm roles: `reader`, `writer`, `admin`
- Clients:
  - `meta-vis-frontend` — public SPA client, PKCE, redirect `http://localhost:5173/*`
  - `meta-vis-backend` — confidential client with a service account (used later
    by the FastAPI backend; secret placeholder in the export)

## Re-exporting after manual changes

If you edit the realm via the admin UI and want to commit the changes, export
from inside the running container:

```bash
docker exec meta-vis-keycloak \
  /opt/keycloak/bin/kc.sh export \
  --dir /tmp/realm-export \
  --realm meta-vis \
  --users realm_file
docker cp meta-vis-keycloak:/tmp/realm-export/meta-vis-realm.json \
  keycloak/realm-export.json
```

Review the diff carefully before committing — Keycloak adds many auto-generated
IDs and timestamps on export.

## Notes

- Storage is the embedded H2 database, persisted in the `keycloak_data` Docker
  volume. Survives `keycloak-down`, wiped by `keycloak-reset`.
- The `--import-realm` flag only imports if the realm does not already exist,
  so editing `realm-export.json` after first start has **no effect** until
  you `make keycloak-reset`.
