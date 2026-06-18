================
Administration
================

Two cross-cutting operational topics: who can do what (**user roles**),
and the record of who did what (**audit log**).

User roles
==========

The app uses three roles — **reader**, **writer**, **admin** — to gate
what users can do. The roles themselves are configured on the Keycloak
client; the app reads them from the access token and enforces
authorization in the API.

Role capability matrix
----------------------

.. list-table::
   :header-rows: 1
   :widths: 40 20 20 20

   * - Capability
     - Reader
     - Writer
     - Admin
   * - View cases, samples, taxonomy
     - ✓
     - ✓
     - ✓
   * - View Krona plots, metaval results
     - ✓
     - ✓
     - ✓
   * - Mark cases reviewed
     - ✗
     - ✓
     - ✓
   * - Add / edit case notes
     - ✗
     - ✓
     - ✓
   * - Add to ignorelists / known-contaminants
     - ✗
     - ✓
     - ✓
   * - Remove from ignorelists / known-contaminants
     - ✗
     - ✗
     - ✓
   * - Delete cases
     - ✗
     - ✗
     - ✓
   * - Curate clinical notes on taxa
     - ✗
     - ✗
     - ✓

Roles ladder up — *writer* implies everything *reader* can do, and
*admin* implies everything *writer* can do.

User accounts
-------------

User identities and role assignments live in **Keycloak**, not in this
app's database. There is no in-app user management screen and no local
password storage.

To grant a user access:

1. The user signs in to the configured Keycloak realm with whatever
   identity provider that realm is federated to (SITHS card, corporate
   SSO, local KC account…).
2. A Keycloak admin assigns the user one of the three client roles
   (``reader`` / ``writer`` / ``admin``) on the app's frontend client.
3. The user logs in to the app. The role is read from the access
   token and drives both the API and the UI.

If a user reaches the login screen successfully but sees a 403 or a
near-empty page after login, they have no role assigned yet. The fix
is in Keycloak, not in this app. See :doc:`../deployment/production`
for the realm configuration the app expects.

User preferences
----------------

Each user can personalise certain UI settings. Preferences are stored
per user (keyed on the Keycloak ``sub`` claim) and persist across
sessions and devices. Open the **Preferences** page by clicking your
username in the bottom-left corner of the sidebar.

Available settings:

Default taxonomy kingdoms
   Which superkingdom(s) are pre-selected in the taxonomy table when
   you open a sample. Any combination of *Bacteria*, *Viruses*,
   *Eukaryota*, *Archaea*. Default: *Viruses*. The kingdom filter on
   the table itself is session-only — changing it temporarily does
   not overwrite your saved preference.

What every user sees
--------------------

There is no per-case or per-user data partitioning. Every user with
any role sees every case in the database. There are also no
field-level permissions — notes written by one user are visible to
every other user. The audit log records which user performed each
write.

If your deployment needs per-case access control, that is not
currently supported.

Audit log
=========

The app records a structured audit trail of every clinically
significant action. Each event is written to **two independent
places**: the application log on stdout (for log aggregation) and the
``audit_log`` MongoDB collection (for compliance review and query).

What is audited
---------------

**Authentication**
   ``login_failed`` — failed Bearer-token validation against the API.
   Successful logins and user-management events are captured by
   Keycloak's own event log, not here.

**Case access and review**
   ``view_case``, ``review_case``, ``unreview_case``, ``add_note``,
   ``delete_note``, ``delete_case``.

**Sample access**
   ``view_sample``.

**Data ingestion**
   ``ingest`` — success or failure.

**Outbreak ignorelist**
   ``ignorelist_add``, ``ignorelist_update``, ``ignorelist_remove``.

**Known pathogens**
   ``pathogen_add``, ``pathogen_remove``.

**NTC ignorelist and contaminants**
   ``ntc_ignorelist_add``, ``ntc_ignorelist_update``,
   ``ntc_ignorelist_remove``, ``ntc_contaminant_add``,
   ``ntc_contaminant_update``, ``ntc_contaminant_remove``.

Event structure
---------------

Each document in ``audit_log`` contains:

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
     - Type of entity affected — ``case``, ``sample``, ``user``, etc.
   * - ``resource_id``
     - string
     - Natural key of the affected resource, e.g. a ``case_id``.
   * - ``outcome``
     - string
     - ``success`` or ``failure``.
   * - ``detail``
     - object or null
     - Optional action-specific context, e.g. the new value on an
       update. Never contains passwords or PHI.

Example:

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

Querying
--------

Connect to MongoDB and query ``audit_log`` directly. Indexes exist on
``timestamp``, ``actor``, ``action``, and ``(resource_type,
resource_id)``, so the queries below stay fast as the log grows.

.. code-block:: javascript

   // Everything that happened to one case
   db.audit_log.find(
     { resource_type: "case", resource_id: "CASE-2026-001" }
   ).sort({ timestamp: -1 })

   // Everything a specific user did
   db.audit_log.find({ actor: "alice" }).sort({ timestamp: -1 })

   // All failed login attempts
   db.audit_log.find({ action: "login_failed" }).sort({ timestamp: -1 })

   // Deletions in the past 30 days
   db.audit_log.find({
     action: { $in: ["delete_case", "ignorelist_remove", "pathogen_remove"] },
     timestamp: { $gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) }
   }).sort({ timestamp: -1 })

Application log
---------------

Every audit event is also written as a structured JSON line on
stdout, with the ``audit`` logger. Forwarding stdout to a log
aggregator (ELK, Loki, CloudWatch, Splunk…) gives you an independent
copy of every event that is unaffected by database failures.

Each line is a single JSON object — same fields as the DB document,
plus ``level: "INFO"`` and ``logger: "audit"``. Request logs (logger
``request``) record every HTTP call with method, path, status code,
duration, and client IP.

Log verbosity is controlled by ``LOG_LEVEL`` in ``backend/.env``
(``debug`` / ``info`` / ``warning`` / ``error`` / ``critical``). Note:
audit events are emitted at ``INFO``, so raising the level to
``warning`` suppresses them from stdout — the ``audit_log`` MongoDB
collection is unaffected and continues to receive all events
regardless of log level.

Protecting the collection in production
---------------------------------------

The ``audit_log`` collection is **append-only by design** — the
application only ever ``insert_one``\\ s. Records are never modified
or deleted by the application. The guarantee only holds if the
database is protected, however:

**Use a dedicated MongoDB server, not the Docker Compose container.**
The dev compose MongoDB stores data in a Docker volume that is
destroyed by ``make reset``. In production, MongoDB must run on a
dedicated server or replica set outside the application's container
lifecycle. See :doc:`../deployment/production`.

**Verify the collection survives redeployment.** Before any deployment
that involves the database, record the current document count, and
check it afterwards:

.. code-block:: bash

   mongosh "mongodb://user:pass@host:27017/meta-vis" \
     --eval "db.audit_log.countDocuments()"

**Back up regularly and test restores.** An audit trail that cannot be
restored from backup provides no compliance guarantee.

**Keep a second copy via the application log.** Stdout-based
forwarding to a log aggregator gives an independent record that
survives a database incident.

Retention
---------

There is no automatic expiry (TTL) on ``audit_log``. For regulated
environments:

- Define a retention period appropriate to your regulatory framework
  (7 years is common in Swedish clinical/hospital contexts).
- Archive older documents to cold storage with
  ``mongodump --collection=audit_log`` rather than deleting them in
  place — that preserves the chain.
- Restrict direct database write access to administrators only. The
  application account needs ``insert`` on ``audit_log`` but not
  ``update`` or ``delete``.
- Consider enabling `MongoDB auditing
  <https://www.mongodb.com/docs/manual/core/auditing/>`_ at the
  database level for a second layer that captures DBA access the
  application cannot see.

See also
========

- :doc:`reviewing-cases` — most audit events come from this workflow
- :doc:`../deployment/production` — Keycloak realm and MongoDB hardening
