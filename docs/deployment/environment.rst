======================
Environment variables
======================

This page is the configuration reference. For step-by-step setup, see
:doc:`local-dev` (development) or :doc:`production` (deployment).

How config is layered
=====================

The backend reads its config from environment variables. Compose loads them
from one or more ``.env`` files; each subsequent file overrides keys defined
earlier. The repo ships three files for three different roles:

==========================  ================  ===================================================
File                        In git?           Purpose
==========================  ================  ===================================================
``backend/.env.example``    yes               Canonical contract — every key the backend expects.
                                              Copy to a gitignored file for a real deploy.
``backend/.env.dev``        yes               Committed dev defaults loaded by compose. Holds
                                              values that are identical for every developer.
``backend/.env``            **no**            Your secrets and per-machine overrides. Overrides
                                              ``.env.dev``. Required for local dev.
==========================  ================  ===================================================

``docker-compose.yml`` loads ``.env.dev`` first, then ``.env`` — so anything
in ``.env`` wins. Service-topology values that are facts of the compose
network (``MONGODB_HOST=mongodb``, ``OBJECT_STORAGE_ENDPOINT=http://minio:9000``)
are set in the compose file's ``environment:`` block, which beats both files.

For production, ``backend/.env.example`` is your starting point — copy it to
``backend/.env.prod`` (gitignored), fill in real values, and point your
runtime at it via ``env_file:`` in ``docker-compose.prod.yml``.

The frontend follows the same pattern: ``frontend/.env.example`` (committed
template), ``frontend/.env`` (gitignored dev config), ``frontend/.env.prod``
(gitignored, used at image-build time). Vite bakes these into the bundle at
build time. The prod image (``frontend/Dockerfile.prod``) additionally
ships an entrypoint script
(``frontend/docker-entrypoint.d/10-inject-env.sh``) that reads the
``VITE_OIDC_*`` keys from the container's environment at startup and
writes them into ``/usr/share/nginx/html/config.js``; the SPA loads that
file before its main bundle and any value found there overrides the
baked-in default. This means OIDC config can be set per environment at
deploy time without a rebuild — see :doc:`production` for the deploy
pattern. ``VITE_API_PROXY_TARGET`` is dev-only and is *not* part of this
runtime-override path.

Backend variables
=================

No localhost fallbacks live in code. Every required key below must be set or
the backend fails fast at startup with a Pydantic validation error.

MongoDB
-------

Pick **either** ``MONGODB_URI`` (preferred for prod) **or** the discrete
host/port/user/password fields. When ``MONGODB_URI`` is set the discrete
fields are ignored.

================================  ==========  ==============================================================
Variable                          Required    Description
================================  ==========  ==============================================================
``MONGODB_URI``                   prod        Full connection string. Carries replicaSet, tls, multiple
                                              seed hosts, query params. Example:
                                              ``mongodb://user:pass@mongo-1:27017,mongo-2:27017/meta-vis?authSource=admin&replicaSet=rs0``
``MONGODB_HOST``                  dev         Hostname or IP, when not using ``MONGODB_URI``.
``MONGODB_PORT``                  dev         Port. Default ``27017``.
``MONGODB_USERNAME``              dev         App user (created by ``mongo-init.js`` in dev).
``MONGODB_PASSWORD``              dev         App user password.
``MONGODB_AUTH_SOURCE``           dev         Auth DB. Usually ``admin``.
``MONGO_ROOT_PASSWORD``           dev only    Root password for the dev MongoDB container.
                                              **Not used in production** — set up your DB user
                                              independently. See :doc:`production`.
``MONGODB_DB_NAME``               yes         Database name (``meta-vis-dev`` / ``meta-vis``).
``MONGODB_DIRECT_CONNECTION``     yes         ``true`` for a single-node replica set behind a port
                                              mapping. ``false`` for a real ``mongodb+srv`` URL or a
                                              multi-host cluster URI.
``MONGODB_USE_TRANSACTIONS``      yes         Wrap ingest + case-mutation writes in a multi-document
                                              transaction. Requires a replica set. Set ``false`` on a
                                              standalone mongod (transactions are rejected otherwise)
                                              and accept that a mid-sequence failure can leave partial
                                              writes behind.
================================  ==========  ==============================================================

Application
-----------

==================  ==========  ==============================================================
Variable            Required    Description
==================  ==========  ==============================================================
``APP_ENV``         yes         ``development`` or ``production``.
``LOG_LEVEL``       yes         One of ``debug``, ``info``, ``warning``, ``error``, ``critical``.
==================  ==========  ==============================================================

Auth (Keycloak / OIDC)
----------------------

The backend validates incoming Bearer tokens against a Keycloak realm. Tokens
are signed by Keycloak — ``JWT_SECRET`` is a legacy field that ``Settings``
still demands but no longer signs anything.

============================  ==========  ==============================================================
Variable                      Required    Description
============================  ==========  ==============================================================
``KEYCLOAK_ISSUER``           yes         Realm public URL. Must equal the ``iss`` claim of incoming
                                          tokens exactly. The SPA also uses this, so use the
                                          browser-facing hostname.
``KEYCLOAK_CLIENT_IDS``       optional    Comma-separated ``azp`` allowlist. Defaults to
                                          ``meta-vis-frontend,meta-vis-cli`` (SPA + ingest CLI). Only
                                          set this to narrow or extend the allowlist; do not drop
                                          ``meta-vis-cli`` unless you also intend to block
                                          ``ingest.py`` uploads.
``KEYCLOAK_ROLE_CLIENT``      yes         KC client whose client-roles drive authorization. Tokens
                                          are inspected at
                                          ``resource_access[<role_client>].roles``.
``KEYCLOAK_JWKS_URL``         optional    Override for the JWKS endpoint. Use when the backend pod
                                          can't reach the public KC hostname. ``iss`` is still
                                          validated against ``KEYCLOAK_ISSUER``.
``JWT_SECRET``                yes         32+ random chars. Legacy. Generate with
                                          ``python -c "import secrets; print(secrets.token_urlsafe(48))"``.
============================  ==========  ==============================================================

CORS
----

================  ==========  ==============================================================
Variable          Required    Description
================  ==========  ==============================================================
``CORS_ORIGINS``  yes         Comma-separated list of allowed origins. List the deployed
                              frontend's origin exactly (scheme + host, no trailing slash).
================  ==========  ==============================================================

Object storage
--------------

Optional. Leave unset to fall back to the MongoDB ``blobs`` collection. See
:doc:`object-storage` for the trade-off.

=================================  ==========  ==============================================================
Variable                           Required    Description
=================================  ==========  ==============================================================
``OBJECT_STORAGE_ENDPOINT``        opt         S3-compatible endpoint. Setting this activates the
                                               S3/MinIO path in ``app/blob_store.py``.
``OBJECT_STORAGE_ACCESS_KEY``      opt         Access key. Required when ``OBJECT_STORAGE_ENDPOINT`` is set.
``OBJECT_STORAGE_SECRET_KEY``      opt         Secret key. Required when ``OBJECT_STORAGE_ENDPOINT`` is set.
``OBJECT_STORAGE_BUCKET``          opt         Bucket name. Default ``meta-vis``.
=================================  ==========  ==============================================================

Optional integrations
---------------------

==========================  ==========  ==============================================================
Variable                    Required    Description
==========================  ==========  ==============================================================
``NCBI_API_KEY``            no          Raises NCBI E-utilities rate limit from 3 to 10 req/s.
``FRESHDESK_BASE_URL``      no          Ticket-link template. Must include ``{ticket_id}``. Leave
                                        unset to disable ticket links in the UI.
==========================  ==========  ==============================================================

Frontend variables
==================

Vite reads ``frontend/.env`` for ``npm run dev`` and ``frontend/.env.prod``
(or ``.env.stage``) for image builds via the ``--mode`` flag. ``VITE_*``
values are baked into the bundle at build time, but the prod image's
startup script re-reads the ``VITE_OIDC_*`` keys below from the
container's environment and overrides the baked-in values with them.
``VITE_API_PROXY_TARGET`` is dev-only and is *not* covered by the
runtime override.

====================================  ==========  ==============================================================
Variable                              Required    Description
====================================  ==========  ==============================================================
``VITE_OIDC_AUTHORITY``               yes         Keycloak realm URL the SPA authenticates against.
``VITE_OIDC_CLIENT_ID``               yes         SPA client ID. Default ``meta-vis-frontend``.
``VITE_OIDC_REDIRECT_URI``            yes         OIDC callback URL. ``<frontend-origin>/auth/callback``.
``VITE_OIDC_POST_LOGOUT_REDIRECT_URI``  yes       Where to land after logout. Usually the SPA root.
``VITE_OIDC_ROLE_CLIENT``             opt         KC client whose client-roles drive UI authz. Defaults to
                                                  ``VITE_OIDC_CLIENT_ID``. Build-time only — the runtime
                                                  override script forwards the four ``VITE_OIDC_*`` keys
                                                  above but not this one.
``VITE_API_PROXY_TARGET``             dev only    Where ``npm run dev`` proxies ``/api/*`` calls. Compose
                                                  overrides this to ``http://backend:8000``. Production
                                                  builds ignore it — the prod nginx config does API proxying.
====================================  ==========  ==============================================================

Generating secrets
==================

.. code-block:: bash

   # JWT_SECRET, MongoDB passwords, anything else random
   python -c "import secrets; print(secrets.token_urlsafe(48))"

Best practices
==============

1. Never commit ``.env``, ``.env.prod``, or ``.env.stage``. The ``.example``
   templates are the only env files that belong in git.
2. Use distinct ``MONGODB_DB_NAME`` values per environment so a misconfigured
   client cannot quietly write into the wrong database.
3. ``CORS_ORIGINS`` is an allowlist — list every public origin explicitly.
   Wildcards are not accepted.
4. In production, source secrets from your platform's secret store
   (Docker secrets, Kubernetes Secrets, Vault) rather than a literal
   ``.env.prod`` file on disk.

Next steps
==========

- :doc:`local-dev` — getting the dev stack running
- :doc:`object-storage` — when to switch from MongoDB blobs to S3
- :doc:`production` — production deployment
