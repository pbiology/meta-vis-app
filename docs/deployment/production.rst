=======================
Production deployment
=======================

This repo ships two things that production consumes:

1. **Container images** for the backend and frontend, built and pushed via
   ``make image-backend-prod`` / ``make image-frontend-prod``.
2. **A canonical environment contract** — ``backend/.env.example`` is the
   list of every variable the backend expects.

It also ships ``docker-compose.prod.yml`` as **one** worked example of how
to run those images on a single host. That file is the basis for this guide.
Other shapes (Kubernetes, OpenShift, systemd-on-a-VM) are equally valid;
adapt the example to your platform.

What this guide assumes
=======================

- A single Linux host with Docker Engine + Compose v2.
- A separate, pre-existing **MongoDB** server (replica set recommended).
  The dev compose file's MongoDB container is **not** suitable for production
  — see :ref:`prod-mongodb` below.
- An existing **Keycloak** instance with a realm you can configure.
- An existing **nginx** (or other reverse proxy) on the host, terminating
  TLS and forwarding the meta-vis hostname to the frontend container at
  ``127.0.0.1:8080``.
- Outbound network access to the image registry (Docker Hub by default).

Pre-deployment checklist
========================

- [ ] MongoDB running on dedicated server(s), with automated backups and a
      tested restore procedure
- [ ] Keycloak realm configured with the SPA and CLI clients (see
      :ref:`prod-keycloak`)
- [ ] TLS certificates issued for the frontend and backend hostnames
- [ ] ``backend/.env.prod`` populated from ``backend/.env.example``
- [ ] ``frontend/.env.prod`` populated from ``frontend/.env.example``
- [ ] Frontend image rebuilt with the production ``.env.prod`` baked in
- [ ] Object storage decided (MongoDB blobs vs S3) and configured
- [ ] Reverse-proxy config in place, including ``X-Forwarded-*`` headers
- [ ] Log aggregation forwarding the backend's stdout off the host
- [ ] Audit-log survival verified end-to-end (see :ref:`audit-log-policy`)

.. _prod-keycloak:

Keycloak configuration
======================

The backend validates incoming Bearer tokens against your Keycloak realm.
You need:

- **One public SPA client** (PKCE, standard flow):

  - ``client_id``: ``meta-vis-frontend`` (or whatever you set as
    ``VITE_OIDC_CLIENT_ID``)
  - Redirect URI: ``https://<frontend-host>/auth/callback``
  - Web origins: the frontend's exact origin (no trailing slash)
  - Client roles: ``reader``, ``writer``, ``admin``

- **One confidential CLI client** for ingest:

  - ``client_id``: ``meta-vis-cli``
  - ``service_accounts_enabled = true``
  - Its service account needs the ``admin`` client role on the SPA client
    (so the CLI's tokens carry authz)
  - Add the SPA client as a **client scope** on the CLI client so the
    service-account token actually contains
    ``resource_access["meta-vis-frontend"].roles``

After applying the realm config, verify the CLI's token includes the role:

.. code-block:: bash

   TOKEN=$(curl -s -d "grant_type=client_credentials" \
       -d "client_id=meta-vis-cli" -d "client_secret=$KEYCLOAK_CLIENT_SECRET" \
       "$KEYCLOAK_ISSUER/protocol/openid-connect/token" \
       | jq -r .access_token)
   echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq .resource_access

Building images
===============

Both images are built and pushed via the Makefile. They target
``linux/amd64`` by default; override ``PLATFORM`` for ARM hosts.

.. code-block:: bash

   make image-backend-prod    # → $BACKEND_IMAGE:prod
   make image-frontend-prod   # → $FRONTEND_IMAGE:prod (uses --mode prod)

By default the images are tagged
``docker.io/clinicalgenomics/metavis-backend:prod`` and
``docker.io/clinicalgenomics/metavis-frontend:prod``. Override the repo with:

.. code-block:: bash

   BACKEND_IMAGE=registry.example.com/meta-vis-backend make image-backend-prod
   FRONTEND_IMAGE=registry.example.com/meta-vis-frontend make image-frontend-prod

.. important::

   **The frontend image is built with its config baked in.** The frontend
   build reads ``frontend/.env.prod`` (loaded automatically by Vite's
   ``--mode prod``) and the resulting bundle hardcodes the OIDC authority,
   API URL, etc. If those values change, you must rebuild the image — there
   is no runtime override.

The ``:prod`` tag is a moving pointer. The Makefile target overwrites it on
every build. For traceability, also push an immutable versioned tag
(``:prod-0.1.0``, ``:prod-<git-sha>``) and reference that from your runtime.

Configuring the backend
=======================

Copy the canonical template and fill it in:

.. code-block:: bash

   cp backend/.env.example backend/.env.prod
   # Edit backend/.env.prod — set MONGODB_URI, KEYCLOAK_*, CORS_ORIGINS,
   # JWT_SECRET, and (if using S3) OBJECT_STORAGE_*.

See :doc:`environment` for the full list of variables and which are required.

Configuring the frontend
========================

The frontend image is built with its config inside. Before
``make image-frontend-prod``:

.. code-block:: bash

   cp frontend/.env.example frontend/.env.prod
   # Edit frontend/.env.prod:
   #   VITE_OIDC_AUTHORITY=https://<kc-host>/realms/<realm>
   #   VITE_OIDC_CLIENT_ID=meta-vis-frontend
   #   VITE_OIDC_REDIRECT_URI=https://<frontend-host>/auth/callback
   #   VITE_OIDC_POST_LOGOUT_REDIRECT_URI=https://<frontend-host>/

Then run the build. The values above are baked into the bundle.

Running the stack
=================

``docker-compose.prod.yml`` runs the two containers, joins them on an
internal bridge network, and binds the frontend to ``127.0.0.1:8080`` so a
host nginx can proxy public traffic to it. Backend is internal only.

.. code-block:: bash

   # Pull and start
   docker compose -f docker-compose.prod.yml pull
   docker compose -f docker-compose.prod.yml up -d

   # Logs
   docker compose -f docker-compose.prod.yml logs -f

   # Stop
   docker compose -f docker-compose.prod.yml down

.. note::

   The shipped ``docker-compose.prod.yml`` references the
   ``clinicalgenomics`` images at the ``:stage`` tag. Override the ``image:``
   field (or the ``BACKEND_IMAGE`` / ``FRONTEND_IMAGE`` makefile defaults)
   for your own deployment. Treat the file as a template, not a hard
   contract.

Reverse proxy
=============

The frontend container serves the built bundle and proxies ``/api/*`` to the
backend container internally. The host nginx only needs to terminate TLS and
forward to ``127.0.0.1:8080``:

.. code-block:: nginx

   server {
       listen 443 ssl http2;
       server_name meta-vis.example.com;

       ssl_certificate     /etc/ssl/certs/meta-vis.crt;
       ssl_certificate_key /etc/ssl/private/meta-vis.key;

       client_max_body_size 100M;   # ingest bundles can be large

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host              $host;
           proxy_set_header X-Real-IP         $remote_addr;
           proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }

   server {
       listen 80;
       server_name meta-vis.example.com;
       return 301 https://$server_name$request_uri;
   }

.. _prod-mongodb:

MongoDB
=======

.. warning::

   The MongoDB container in ``docker-compose.yml`` (the dev stack) is for
   **development only**. A single container has no replication, no automated
   backups, and its data is destroyed by ``docker compose down -v``. The
   ``audit_log`` collection in particular is a compliance record that must
   not be exposed to that risk.

Recommended topology
--------------------

A three-node MongoDB 7.0 replica set on dedicated VMs. It provides:

- Automatic failover if the primary node goes down
- A readable secondary for backups without impacting the primary
- Point-in-time recovery via the oplog

Point the backend at it via ``MONGODB_URI``:

.. code-block:: ini

   MONGODB_URI=mongodb://meta-vis-app:<pw>@vm1.internal:27017,vm2.internal:27017,vm3.internal:27017/meta-vis?authSource=admin&replicaSet=rs0
   MONGODB_DB_NAME=meta-vis
   MONGODB_DIRECT_CONNECTION=false
   MONGODB_USE_TRANSACTIONS=true

For a standalone mongod, set ``MONGODB_USE_TRANSACTIONS=false`` — multi-doc
transactions are rejected without a replica set, and ingest will fail
otherwise.

Creating the application user
-----------------------------

Run the following in the MongoDB shell as an admin user:

.. code-block:: javascript

   use admin
   db.createUser({
     user: "meta-vis-app",
     pwd:  "<MONGODB_PASSWORD>",
     roles: [{ role: "readWrite", db: "meta-vis" }]
   })

For tighter security, grant ``read`` + ``insert`` on ``audit_log`` only (no
``update`` or ``delete``), and ``readWrite`` on the remaining collections.
This prevents any code path — including a compromised application account —
from modifying or deleting audit records.

The backend's ``_ensure_indexes()`` runs at startup and is idempotent — it
creates any missing indexes on the target server without touching existing
data. No migration step is required when pointing at a new database.

Object storage in production
============================

In production prefer S3-compatible object storage over the MongoDB ``blobs``
collection — Krona HTML and IGV reports are large and bloat the database
working set. Set the four ``OBJECT_STORAGE_*`` variables in
``backend/.env.prod`` and ensure the configured bucket exists. See
:doc:`object-storage` for details.

Logging
=======

The backend emits structured JSON lines on stdout (one JSON object per
line). In production, stdout **must** be routed to a persistent destination
— logs written only to a container's stdout are lost when the container
restarts.

.. code-block:: bash

   docker compose -f docker-compose.prod.yml logs -f backend

Forward the container's stdout to a log aggregator (ELK/OpenSearch, Loki,
CloudWatch, Splunk, etc.). This gives you an independent copy of every
audit event in addition to the ``audit_log`` MongoDB collection — useful if
the database is unreachable during an incident investigation.

To alert on audit-write failures, watch for log lines containing:

.. code-block:: text

   "message": "Failed to write audit event to database"

This means the ``audit_log`` collection is not receiving events and
requires immediate attention.

Metrics worth monitoring:

- API response times and error rates
- MongoDB query latency
- Storage usage (MongoDB + S3)
- Failed login attempts (``action: "login_failed"`` in ``audit_log``)

.. _audit-log-policy:

Audit-log integrity policy
==========================

The ``audit_log`` collection is a compliance record. Treat it accordingly:

- **Before any deployment that touches the database** (schema change,
  index rebuild, server move), record the current document count and
  verify it after:

  .. code-block:: bash

     mongosh "<MONGODB_URI>" --eval "db.audit_log.countDocuments()"

  If the count drops unexpectedly, stop and investigate.
- **Back up ``audit_log`` independently** of the rest of the database, so
  you can restore it without reverting recent application state.
- **Forward audit events to your log aggregator** as a second, independent
  copy.

Backups and disaster recovery
=============================

Back up the entire database with ``mongodump``. From a machine with network
access to the MongoDB server:

.. code-block:: bash

   # Full database backup
   mongodump \
     --uri="<MONGODB_URI>" \
     --out=/backups/mongo-$(date +%Y%m%d)

   # audit_log only (compliance snapshot)
   mongodump \
     --uri="<MONGODB_URI>" \
     --collection=audit_log \
     --out=/backups/audit-$(date +%Y%m%d)

Store backups off-host. A backup held on the same VM as the database is not
a backup — it is lost in the same failure.

For a replica set, target a secondary to avoid impact on the primary:

.. code-block:: bash

   mongodump \
     --uri="mongodb://user:pass@vm2.internal:27017/meta-vis?authSource=admin&readPreference=secondary" \
     --out=/backups/mongo-$(date +%Y%m%d)

Verify backups monthly by restoring to a scratch database and spot-checking:

.. code-block:: bash

   mongorestore \
     --uri="mongodb://user:pass@testhost:27017/?authSource=admin" \
     --nsFrom="meta-vis.*" \
     --nsTo="meta-vis-restore.*" \
     /backups/mongo-YYYYMMDD

   mongosh "mongodb://user:pass@testhost:27017/meta-vis-restore" \
     --eval "db.audit_log.countDocuments()"

A backup that has never been tested is not a backup.

**Targets:**

- RTO (Recovery Time Objective): < 4 hours
- RPO (Recovery Point Objective): < 1 day, or < 1 hour with a replica-set oplog

Upgrade flow
============

1. Build and push new versioned image tags
   (``make image-backend-prod`` / ``make image-frontend-prod``, with an
   immutable ``:prod-<version>`` tag).
2. Update the ``image:`` references in ``docker-compose.prod.yml`` (or your
   ops repo) to the new tag.
3. ``docker compose -f docker-compose.prod.yml pull``
4. ``docker compose -f docker-compose.prod.yml up -d`` — recreates only the
   containers whose images changed.
5. Verify the backend is healthy (``/docs`` returns 200) and the
   ``audit_log`` count hasn't regressed.

Mutable ``:prod`` tags + ``imagePullPolicy: Always`` are unreliable for
in-place updates. Use immutable versioned tags and bump the tag explicitly.

Next steps
==========

- :doc:`environment` — the full environment variable reference
- :doc:`object-storage` — switching between MongoDB blobs and S3
- :doc:`../administration/audit-log` — what the audit log captures
