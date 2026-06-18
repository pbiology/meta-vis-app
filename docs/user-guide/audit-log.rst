=========
Audit Log
=========

meta-vis-app records a structured audit trail of all clinically significant
actions. Every event is written to both the application log (stdout) and a
dedicated ``audit_log`` MongoDB collection, providing two independent paths for
compliance review and incident investigation.

What is audited
===============

**Authentication**

- Failed login attempts (``login_failed``) — records the attempted username

**Case access and review**

- Viewing a case (``view_case``)
- Marking a case as reviewed (``review_case``)
- Removing a review (``unreview_case``)
- Adding a note to a case (``add_note``)
- Deleting a note from a case (``delete_note``)
- Deleting a case and all associated data (``delete_case``)

**Sample access**

- Viewing a sample (``view_sample``)

**Data ingestion**

- Ingest success and failure (``ingest``)

**Outbreak ignorelist**

- Adding a taxon to the outbreak ignorelist (``ignorelist_add``)
- Updating an ignorelist entry (``ignorelist_update``)
- Removing a taxon from the ignorelist (``ignorelist_remove``)

**Known pathogens**

- Adding a taxon to the known pathogens list (``pathogen_add``)
- Removing a taxon from the known pathogens list (``pathogen_remove``)

**NTC ignorelist and contaminants**

- Adding / updating / removing NTC ignorelist entries (``ntc_ignorelist_add``, ``ntc_ignorelist_update``, ``ntc_ignorelist_remove``)
- Adding / updating / removing known contaminants (``ntc_contaminant_add``, ``ntc_contaminant_update``, ``ntc_contaminant_remove``)

User management (creation, role changes, deletion) happens in Keycloak and
is audited there, not here. Keycloak also records successful logins in its
own event log; this app only records failed Bearer-token validation against
the API as ``login_failed``.

Audit event structure
=====================

Each event in the ``audit_log`` collection contains:

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Field
     - Type
     - Description
   * - ``timestamp``
     - Date (UTC)
     - When the event occurred. Stored as a BSON ``Date`` for precise querying.
   * - ``action``
     - string
     - The action performed (see list above).
   * - ``actor``
     - string
     - Username of the user who performed the action.
   * - ``resource_type``
     - string
     - The type of entity affected, e.g. ``case``, ``sample``, ``user``.
   * - ``resource_id``
     - string
     - The natural key of the affected resource, e.g. a ``case_id``.
   * - ``outcome``
     - string
     - Either ``success`` or ``failure``.
   * - ``detail``
     - object or null
     - Optional action-specific context, e.g. the new role on a role change. Never contains passwords or PHI.

Example document:

.. code-block:: json

   {
     "timestamp": "2026-04-12T09:15:00.123Z",
     "action": "review_case",
     "actor": "alice",
     "resource_type": "case",
     "resource_id": "CASE-2026-001",
     "outcome": "success",
     "detail": { "notes": true }
   }

Querying the audit log
======================

Connect to MongoDB and query the ``audit_log`` collection directly.

**All events for a specific case:**

.. code-block:: javascript

   db.audit_log.find(
     { resource_type: "case", resource_id: "CASE-2026-001" }
   ).sort({ timestamp: -1 })

**Everything a specific user did:**

.. code-block:: javascript

   db.audit_log.find(
     { actor: "alice" }
   ).sort({ timestamp: -1 })

**All failed login attempts:**

.. code-block:: javascript

   db.audit_log.find(
     { action: "login_failed" }
   ).sort({ timestamp: -1 })

**All deletions in the past 30 days:**

.. code-block:: javascript

   db.audit_log.find({
     action: { $in: ["delete_case", "ignorelist_remove", "pathogen_remove"] },
     timestamp: { $gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) }
   }).sort({ timestamp: -1 })

**Who viewed a sample:**

.. code-block:: javascript

   db.audit_log.find(
     { action: "view_sample", resource_id: "<sample_object_id>" }
   ).sort({ timestamp: -1 })

The collection has indexes on ``timestamp``, ``actor``, ``action``, and
``(resource_type, resource_id)`` — all queries above will use an index and
remain fast as the log grows.

Application logging
===================

In addition to the database collection, all audit events — and all application
activity — are written as structured JSON lines to stdout. This output is
suitable for ingestion by any log aggregation system (e.g. CloudWatch, Splunk,
Elastic, Loki).

Each log line is a single JSON object:

.. code-block:: json

   {
     "timestamp": "2026-04-12T09:15:00.123456+00:00",
     "level": "INFO",
     "logger": "audit",
     "message": "review_case",
     "action": "review_case",
     "actor": "alice",
     "resource_type": "case",
     "resource_id": "CASE-2026-001",
     "outcome": "success",
     "detail": { "notes": true }
   }

Request logs (from the ``request`` logger) record every HTTP call:

.. code-block:: json

   {
     "timestamp": "2026-04-12T09:15:00.089+00:00",
     "level": "INFO",
     "logger": "request",
     "message": "PATCH /api/v1/cases/CASE-2026-001/review",
     "method": "PATCH",
     "path": "/api/v1/cases/CASE-2026-001/review",
     "status_code": 200,
     "duration_ms": 14.3,
     "client_ip": "10.0.1.5"
   }

Controlling log verbosity
=========================

Set ``LOG_LEVEL`` in ``backend/.env``:

.. code-block:: ini

   LOG_LEVEL=info

Valid values (case-insensitive): ``debug``, ``info``, ``warning``, ``error``, ``critical``.

.. note::

   Audit events are always emitted at ``INFO`` level. Setting ``LOG_LEVEL=warning``
   will suppress request logs and other informational output but will also suppress
   audit log lines from stdout. The ``audit_log`` MongoDB collection is unaffected
   by the log level — events are always written there regardless.

Protecting the collection in production
========================================

The ``audit_log`` collection is **append-only** by design — the application
only ever calls ``insert_one`` on it. Records are never modified or deleted by
the application. However, this guarantee only holds if the database itself is
protected.

**Use a dedicated MongoDB server, not the Docker Compose container**

The ``docker-compose.yml`` MongoDB container stores data in a Docker volume
that is destroyed by ``docker compose down -v``. In production, MongoDB must
run on a dedicated server or replica set outside the application container
lifecycle. See :doc:`../deployment/production` for setup instructions.

**Verify the collection survives redeployment**

Before any deployment that involves the database, record the current document
count:

.. code-block:: bash

   mongosh "mongodb://user:pass@host:27017/meta-vis" \
     --eval "db.audit_log.countDocuments()"

Check the same count after deployment to confirm no data was lost.

**Back up regularly and test restores**

A clinical audit trail that cannot be restored from backup provides no
compliance guarantee. See :doc:`../deployment/production` for backup procedures
and monthly restore testing.

**Second copy via application logs**

Every audit event is also written as a JSON line to stdout. If stdout is
collected by a log aggregation system (ELK, Loki, CloudWatch, etc.), you have
an independent copy of every event that is unaffected by database failures or
accidental data loss. Set this up before going live.

Retention and compliance
========================

There is no automatic expiry (TTL) on ``audit_log``. For regulated environments:

- Define a retention period appropriate to your regulatory framework (e.g. 7 years is common in Swedish clinical/hospital contexts).
- Implement archival by exporting older documents to cold storage (``mongodump --collection=audit_log``) rather than deleting in-place, preserving the chain of records.
- Restrict direct database write access to administrators only — the application account needs ``insert`` on ``audit_log`` but not ``update`` or ``delete``.
- Consider enabling `MongoDB auditing <https://www.mongodb.com/docs/manual/core/auditing/>`_ at the database level for a second independent layer that captures DBA-level access the application cannot see.
