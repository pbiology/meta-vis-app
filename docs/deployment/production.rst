=======================
Production Deployment
=======================

This guide covers deploying meta-vis-app to a production environment.

Pre-deployment checklist
========================

- [ ] SSL/TLS certificates configured
- [ ] MongoDB running on dedicated server(s), not the Docker Compose container
- [ ] MongoDB connection URI set in ``.env`` (``MONGODB_HOST`` or full URI)
- [ ] MongoDB automated backups configured and a restore tested end-to-end
- [ ] ``audit_log`` collection verified to survive a full app redeployment
- [ ] Object storage configured (S3 or MinIO)
- [ ] Application logs (stdout) routed to a persistent destination
- [ ] Email alerting configured (if desired)
- [ ] Monitoring and logging set up
- [ ] Database and application secrets secured
- [ ] User authentication provider configured (if SSO used)
- [ ] Firewall rules allow required ports
- [ ] Load balancing configured (if multi-instance)

Security considerations
=======================

1. **Environment variables** - Use secrets management (Docker secrets, Kubernetes secrets, environment service)
2. **JWT secret** - Must be long, random, and securely generated. Never hardcode.
3. **Database authentication** - Use strong passwords, restrict network access
4. **API authentication** - All API calls require valid JWT tokens
5. **HTTPS only** - Configure TLS/SSL for all traffic
6. **Firewall rules** - Only expose ports 80/443 for HTTPS, restrict MongoDB/MinIO access to internal networks

Backend deployment
==================

**Using Docker:**

.. code-block:: bash

   docker run -d \
     --name meta-vis-app \
     -p 8000:8000 \
     --env-file .env \
     -v /data/uploads:/app/uploads \
     meta-vis-app:latest

**Using systemd:**

Create ``/etc/systemd/system/meta-vis-app.service``:

.. code-block:: ini

   [Unit]
   Description=meta-vis-app backend
   After=network.target mongodb.service

   [Service]
   Type=simple
   User=meta-vis
   WorkingDirectory=/opt/meta-vis-app
   EnvironmentFile=/opt/meta-vis-app/.env
   ExecStart=/opt/meta-vis-app/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target

Frontend deployment
===================

**Build for production:**

.. code-block:: bash

   cd frontend
   npm run build

This creates an optimized ``dist/`` directory.

**Serve with nginx:**

.. code-block:: nginx

   server {
       listen 443 ssl http2;
       server_name meta-vis.example.com;

       ssl_certificate /etc/ssl/certs/meta-vis.crt;
       ssl_certificate_key /etc/ssl/private/meta-vis.key;

       # Serve static frontend assets
       root /opt/meta-vis-app/frontend/dist;
       index index.html;

       # React Router: route all non-file requests to index.html
       location / {
           try_files $uri $uri/ /index.html;
       }

       # Proxy API requests to backend
       location /api/ {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }

   # Redirect HTTP to HTTPS
   server {
       listen 80;
       server_name meta-vis.example.com;
       return 301 https://$server_name$request_uri;
   }

**Using Docker:**

.. code-block:: dockerfile

   FROM node:18 as build
   WORKDIR /app
   COPY frontend/package*.json ./
   RUN npm ci
   COPY frontend ./
   RUN npm run build

   FROM nginx:alpine
   COPY --from=build /app/dist /usr/share/nginx/html
   COPY nginx.conf /etc/nginx/conf.d/default.conf
   EXPOSE 80
   CMD ["nginx", "-g", "daemon off;"]

MongoDB deployment
==================

.. warning::

   The ``docker-compose.yml`` MongoDB container is intended for **development
   only**. Never use it as your production database — a single container has no
   replication, no automated backups, and its data is destroyed by
   ``docker compose down -v``. The ``audit_log`` collection in particular is a
   compliance record that must not be at risk from a routine deployment step.

**Recommended: dedicated server(s)**

The intended production topology is a standalone MongoDB 7.0 server or a
three-node replica set running on dedicated VMs. The application connects to it
via a standard MongoDB URI in ``.env`` — no code changes are required to switch
from the Docker container to an external server.

Switching from the Docker container to a dedicated MongoDB server:

1. Set up MongoDB on the target server(s) and create the application database
   and user (see :ref:`mongo-user-setup` below).
2. Update ``MONGODB_HOST`` (and optionally ``MONGODB_PORT``) in
   ``backend/.env`` to point at the new server. For a replica set, supply the
   full connection URI directly — Motor (the MongoDB driver) accepts any valid
   MongoDB URI string.
3. Restart the application. ``_ensure_indexes()`` runs at startup and is
   idempotent — it will create any missing indexes on the new server without
   touching existing data.
4. Decommission the Docker container only after verifying the application is
   healthy against the new server.

.. _mongo-user-setup:

**Creating the application user on a dedicated MongoDB server**

Run the following in the MongoDB shell as an admin user:

.. code-block:: javascript

   use admin
   db.createUser({
     user: "<MONGODB_USERNAME>",
     pwd:  "<MONGODB_PASSWORD>",
     roles: [{ role: "readWrite", db: "<MONGODB_DB_NAME>" }]
   })

For tighter security, grant ``read`` + ``insert`` on ``audit_log`` only (no
``update`` or ``delete``), and ``readWrite`` on the remaining collections.
This prevents any code path — including a compromised application account —
from modifying or deleting audit records.

**Replica set (three-node)**

A three-node replica set is the recommended production topology. It provides:

- Automatic failover if the primary node goes down
- A readable secondary for backup operations without impacting the primary
- Point-in-time recovery via the oplog

When using a replica set, supply the full connection URI in ``.env``:

.. code-block:: ini

   MONGODB_HOST=vm1.internal:27017,vm2.internal:27017,vm3.internal:27017

Motor discovers all nodes from the URI and handles failover automatically.

**Minimum specs (single node):**

- 4 GB RAM
- 20 GB SSD storage (adjust for case volume — see :doc:`../administration/audit-log` for sizing guidance)
- Daily automated backups

Monitoring and logging
======================

**Application logs**

The backend emits structured JSON lines on stdout (one JSON object per line).
In production, stdout must be routed to a persistent destination — logs written
only to a container's stdout are lost when the container restarts.

.. code-block:: bash

   # View live logs (Docker)
   docker logs -f meta-vis-app

   # View live logs (systemd)
   journalctl -u meta-vis-app -f

Configure your deployment to forward stdout to a log aggregation system
(ELK/OpenSearch, Loki, CloudWatch, Splunk, etc.). This gives you a second,
independent copy of all audit events in addition to the ``audit_log`` MongoDB
collection — useful if database access is unavailable during an incident
investigation.

To alert on audit write failures, watch for log lines containing:

.. code-block:: text

   "message": "Failed to write audit event to database"

This indicates the MongoDB ``audit_log`` collection is not receiving events and
requires immediate attention.

**Metrics to monitor:**

- API response times
- Database query performance
- Storage usage (MongoDB + S3)
- Blob upload/download times
- Error rates
- Failed login attempts (``action: "login_failed"`` in ``audit_log``)

**Tools:**

- Prometheus + Grafana (metrics and dashboards)
- ELK Stack / OpenSearch (logs)
- Sentry (error tracking)
- New Relic, Datadog, etc. (managed solutions)

Performance tuning
==================

**Backend:**

.. code-block:: bash

   # Increase workers for parallel requests
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 8

**Database:**
- Enable indexing on frequently queried fields
- Monitor slow queries
- Consider read replicas for read-heavy workloads

**Frontend:**
- Enable gzip compression in nginx
- Cache static assets with long TTLs
- Use a CDN for global distribution

Scaling considerations
======================

**Horizontal scaling (multiple servers):**
- Load balance requests with nginx or HAProxy
- Use managed MongoDB (no local database)
- Use shared object storage (MinIO cluster or AWS S3)
- Ensure sessions don't rely on local state

**Vertical scaling (bigger server):**
- Increase backend workers
- Allocate more RAM to MongoDB
- Use faster disk storage (SSD)

Disaster recovery
==================

**Backups**

Back up the entire MongoDB database with ``mongodump``. Run this from a machine
with network access to the MongoDB server:

.. code-block:: bash

   # Full database backup
   mongodump \
     --uri="mongodb://user:pass@host:27017/meta-vis?authSource=admin" \
     --out=/backups/mongo-$(date +%Y%m%d)

   # audit_log only (for a quick compliance snapshot)
   mongodump \
     --uri="mongodb://user:pass@host:27017/meta-vis?authSource=admin" \
     --collection=audit_log \
     --out=/backups/audit-$(date +%Y%m%d)

Store backups off-site (a separate server, S3 bucket, or tape). A backup held
on the same VM as the database is not a backup — it is lost in the same failure.

If running a replica set, run ``mongodump`` against a secondary node to avoid
any impact on the primary:

.. code-block:: bash

   mongodump \
     --uri="mongodb://user:pass@vm2.internal:27017/meta-vis?authSource=admin&readPreference=secondary" \
     --out=/backups/mongo-$(date +%Y%m%d)

**Backup frequency:**

- Daily full backup (the database is small — see :doc:`../administration/audit-log` for sizing)
- Retain daily backups for 30 days, monthly backups for the duration of your retention policy

**Verifying backups**

A backup that has never been tested is not a backup. Monthly, restore to a
scratch database and verify the collections are intact:

.. code-block:: bash

   # Restore to a test database
   mongorestore \
     --uri="mongodb://user:pass@testhost:27017/?authSource=admin" \
     --nsFrom="meta-vis.*" \
     --nsTo="meta-vis-restore.*" \
     /backups/mongo-YYYYMMDD

   # Spot-check audit_log
   mongosh "mongodb://user:pass@testhost:27017/meta-vis-restore" \
     --eval "db.audit_log.countDocuments()"

**Protecting the audit_log collection specifically**

Before decommissioning or redeploying any component, verify the ``audit_log``
collection is intact on the production database:

.. code-block:: bash

   mongosh "mongodb://user:pass@host:27017/meta-vis" \
     --eval "db.audit_log.countDocuments()"

Compare this count against the previous backup. If the count drops unexpectedly,
stop and investigate before proceeding.

**RTO/RPO targets:**

- Recovery Time Objective (RTO): < 4 hours
- Recovery Point Objective (RPO): < 1 day (< 1 hour if using a replica set oplog)

Next steps
==========

- Work with DevOps/infrastructure team for your environment
- Set up monitoring and alerting
- Test disaster recovery procedures
- Document your deployment for the operations team
