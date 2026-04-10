=======================
Production Deployment
=======================

This guide covers deploying meta-vis-app to a production environment.

Pre-deployment checklist
========================

- [ ] SSL/TLS certificates configured
- [ ] MongoDB backed up and recovery tested
- [ ] Object storage configured (S3 or MinIO)
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

**Managed services (recommended):**
- MongoDB Atlas (cloud-hosted)
- AWS DocumentDB
- Azure Cosmos DB
- Google Cloud Firestore

**Self-hosted (advanced):**
- Use official MongoDB Docker image
- Configure replication for high availability
- Set up automated backups
- Monitor disk usage and performance

**Minimum specs:**
- 4 GB RAM
- 20 GB SSD storage (adjust for case volume)
- Daily automated backups

Monitoring and logging
======================

**Application logs:**

.. code-block:: bash

   # View backend logs
   docker logs -f meta-vis-app

   # Or with systemd
   journalctl -u meta-vis-app -f

**Metrics to monitor:**
- API response times
- Database query performance
- Storage usage (MongoDB + S3)
- Blob upload/download times
- Error rates
- User authentication failures

**Tools:**
- Prometheus + Grafana (metrics and dashboards)
- ELK Stack (logs)
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

**Regular backups:**

.. code-block:: bash

   # MongoDB
   mongodump --uri="mongodb://user:pass@host:27017/meta-vis" --out=/backups/mongo-$(date +%Y%m%d)

   # S3
   aws s3 sync s3://meta-vis-prod /backups/s3-$(date +%Y%m%d)

**Backup frequency:**
- Daily incremental
- Weekly full
- Monthly long-term archive

**Recovery testing:**
- Test backup restoration monthly
- Document recovery procedures
- Maintain runbooks for common incidents

**RTO/RPO targets:**
- Recovery Time Objective (RTO): < 4 hours
- Recovery Point Objective (RPO): < 1 day

Next steps
==========

- Work with DevOps/infrastructure team for your environment
- Set up monitoring and alerting
- Test disaster recovery procedures
- Document your deployment for the operations team
