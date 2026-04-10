===========
Performance
===========

Performance considerations and optimization strategies.

Overview
========

meta-vis-app is designed to scale efficiently. This guide covers monitoring and tuning.

Bottleneck analysis
===================

**Identify slow requests:**

1. Check browser Network tab (F12 → Network)
2. Look for slow API calls
3. Check backend logs
4. Use MongoDB profiler

**Common bottlenecks:**

- Large taxonomy queries (too many organisms)
- Unindexed MongoDB queries
- File I/O during ingest
- Insufficient server resources

Backend performance
===================

**Monitoring:**

.. code-block:: bash

   # Monitor system resources
   top                    # CPU, memory
   iotop                  # Disk I/O
   
   # MongoDB profiling
   mongosh
   > db.setProfilingLevel(1)  # Enable profiling
   > db.system.profile.find().sort({ ts: -1 }).limit(5)

**Optimization:**

**Increase workers:**

.. code-block:: bash

   uvicorn app.main:app --workers 8

More workers = more concurrent requests. Set to: (CPU cores × 2) + 1

**Connection pooling:**

Backend already uses Motor (async driver). Verify pool size in code if needed.

**Caching:**

Outbreak alerts cached for 1 hour. Could add:
- Redis for distributed caching (multiple instances)
- Memcached for simple cases
- In-memory cache for taxonomy queries

**Async operations:**

Ensure all I/O is async:

.. code-block:: python

   # Good - async
   async def get_case(case_id: str):
       return await db.cases.find_one({"case_id": case_id})
   
   # Bad - blocking
   def get_case(case_id: str):
       return db.cases.find_one({"case_id": case_id})

Database performance
====================

**Indexing:**

Check existing indexes:

.. code-block:: bash

   mongosh
   > db.cases.getIndexes()

Add missing indexes:

.. code-block:: javascript

   // For frequent queries
   db.samples.createIndex({ "case_id": 1 })
   db.samples.createIndex({ "order_date": -1 })
   
   // For text search
   db.taxa.createIndex({ "name": "text" })

**Query optimization:**

.. code-block:: javascript

   // Bad - scans full collection
   db.samples.find({ name: "Influenza" })
   
   // Good - uses index
   db.samples.find({ case_id: "case-001" })

**Projection:**

Fetch only needed fields:

.. code-block:: javascript

   // Bad - returns entire document
   db.cases.findOne({ case_id: "case-001" })
   
   // Good - returns only needed fields
   db.cases.findOne(
     { case_id: "case-001" },
     { projection: { case_id: 1, reviewed: 1 } }
   )

**Connection issues:**

If queries slow down over time:

.. code-block:: bash

   # Restart MongoDB
   docker compose restart mongodb
   
   # Check database size
   mongosh
   > db.stats()

**Sharding (advanced):**

For very large deployments (1000+ cases):
- Consider MongoDB sharding
- Shard key: case_id or case_id + date range
- Discuss with DevOps team

Frontend performance
====================

**Bundle size:**

Check what's being bundled:

.. code-block:: bash

   cd frontend
   npm run build
   ls -lh dist/
   
   # Analyze bundle
   npm install --save-dev rollup-plugin-visualizer
   # Then check build output

**Optimization:**

- **Code splitting** - Split routes into separate chunks
- **Lazy loading** - Load heavy components on demand
- **Image optimization** - Compress images
- **Tree shaking** - Remove unused code

**Caching:**

Set cache headers in nginx:

.. code-block:: nginx

   location ~* \.(js|css|png|jpg)$ {
       expires 1y;
       add_header Cache-Control "public, immutable";
   }

**Monitoring:**

Use Lighthouse (F12 → Lighthouse):
- Performance score
- Largest Contentful Paint (LCP)
- First Input Delay (FID)
- Cumulative Layout Shift (CLS)

Ingestion performance
=====================

**Large cases (100+ samples):**

Ingestion can take 15–30 minutes. This is normal.

**Optimization:**

- Run during off-peak hours
- Use ``--quiet`` flag to reduce output
- Parallel ingestion:

  .. code-block:: bash

     # Run 2 ingestions in parallel
     ingest_case_1.sh &
     ingest_case_2.sh &
     wait

**Monitoring ingestion:**

.. code-block:: bash

   # Watch progress
   tail -f ingest.log
   
   # Monitor resources
   top
   iostat 1

Outbreak detection scaling
==========================

**How it scales:**

The aggregation pipeline is bounded by time window, not total cases:

.. code-block:: text

   Time window | Cases processed | Query time
   7 days      | ~200 cases      | 200–500ms
   14 days     | ~400 cases      | 400–1000ms
   30 days     | ~1000 cases     | 800–2000ms

**Optimization:**

Results are cached for 1 hour:
- First request: 800–2000ms
- Subsequent requests: 0ms (from cache)

For distributed systems:
- Use Redis for shared cache
- Invalidate when case ingested
- Invalidate when ignorelist changed

Storage optimization
====================

**Object storage:**

Krona HTML files are 1–2 MB each. With 500 cases × 3 classifiers:

.. code-block:: text

   MongoDB backend:  1.5–3 GB in database
   S3 backend:       1.5–3 GB in object storage
   Total disk:       ~5 GB

**Cleanup options:**

- Archive old cases (export and delete)
- Delete Krona files if not needed (regenerate if needed)
- Use S3 lifecycle policies to archive old blobs

**Backup storage:**

Daily backups can accumulate:
- 3 months = 450 GB
- 1 year = 1.8 TB

Implement retention policy:
- Keep daily for 30 days
- Keep weekly for 3 months
- Keep monthly for 1 year

Resource requirements
====================

**Minimum (small deployment, < 100 cases):**

- CPU: 2 cores
- RAM: 4 GB
- Storage: 50 GB

**Recommended (medium, 100–1000 cases):**

- CPU: 4 cores
- RAM: 8 GB
- Storage: 500 GB
- Network: 100 Mbps

**Large (1000+ cases):**

- CPU: 8+ cores
- RAM: 16+ GB
- Storage: 2+ TB
- Network: 1 Gbps

MongoDB specific tuning
=======================

**RAM allocation:**

MongoDB uses RAM for cache. Allocate ~50% of available RAM:

.. code-block:: bash

   # In docker-compose.yml
   mem_limit: 8g  # If host has 16GB

**Journal:**

MongoDB writes journal to disk for durability. This is I/O intensive.

Tune with:

.. code-block:: javascript

   db.adminCommand({ setParameter: 1, journalCommitInterval: 500 })

Higher value = faster, more data loss risk if crash

**Slow query logging:**

Find slow queries:

.. code-block:: javascript

   db.setProfilingLevel(1)  // Log operations > 100ms
   db.system.profile.find({ millis: { $gt: 100 } }).sort({ ts: -1 }).limit(10)

Benchmarking
============

**Benchmark a query:**

.. code-block:: bash

   mongosh
   > const start = Date.now();
   > db.samples.find({ case_id: "case-001" }).toArray();
   > const end = Date.now();
   > console.log(`Query took ${end - start}ms`);

**Benchmark API endpoint:**

.. code-block:: bash

   # Before optimization
   time curl http://localhost:8000/api/cases
   
   # After optimization
   time curl http://localhost:8000/api/cases

**Load testing:**

For production-like testing:

.. code-block:: bash

   pip install locust
   # Create locustfile.py with load test scenarios
   locust -f locustfile.py

Monitoring tools
================

**Open source:**

- **Prometheus** - Metrics collection
- **Grafana** - Dashboards
- **ELK Stack** - Logging (Elasticsearch, Logstash, Kibana)

**Managed services:**

- **New Relic** - APM and infrastructure monitoring
- **Datadog** - Infrastructure and application monitoring
- **CloudWatch** (AWS) - Metrics and logging
- **Azure Monitor** - Monitoring for Azure deployments

**Alerts to set up:**

- CPU > 80%
- RAM > 85%
- Disk > 90%
- API response time > 2s
- MongoDB connections at limit
- Ingest failures

Troubleshooting slow performance
===============================

**Is it the database?**

.. code-block:: bash

   # Slow queries
   mongosh
   > db.currentOp()  // Shows current operations
   > db.setProfilingLevel(1)

**Is it the backend?**

.. code-block:: bash

   # Check resource usage
   docker stats meta-vis-app
   
   # View application logs
   docker logs -f meta-vis-app

**Is it the frontend?**

.. code-block:: bash

   # Browser DevTools
   F12 → Network → Watch request times
   F12 → Performance → Profile page load

**Is it the network?**

.. code-block:: bash

   # Check latency
   ping backend-server
   
   # Check bandwidth
   iperf3 -c backend-server

Next steps
==========

- :doc:`architecture` - System design
- :doc:`deployment/production` - Production configuration
- Start monitoring your deployment
