===========
User roles
===========

meta-vis-app uses three roles — **reader**, **writer**, **admin** — to gate
what users can do inside the app. The roles themselves are configured on
the Keycloak client; the app reads them from the access token and enforces
authorization in the API.

Role capability matrix
======================

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

Reader
------

Read-only access to everything users with higher roles can see. Suitable
for a colleague who needs to look at results but should not be able to
edit notes or change review state.

Writer
------

Everything a reader can do, plus the day-to-day clinical-review actions:
mark cases reviewed, edit notes, manage list entries. This is the role
most clinical microbiologists should have.

Admin
-----

Everything a writer can do, plus destructive and curatorial actions: case
deletion, list-entry removal, and curation of clinical notes on taxa.

User accounts
=============

User identities and role assignments live in **Keycloak**, not in this
app's database. There is no in-app user management screen and no local
password storage.

To grant a user access:

1. The user signs in to the configured Keycloak realm with whatever
   identity provider that realm is federated to (SITHS card, corporate
   SSO, local KC account…).
2. A Keycloak admin assigns the user one of the three client roles
   (``reader`` / ``writer`` / ``admin``) on the app's frontend client.
3. The user logs in to the app. The role is read from the access token
   and drives both the API and the UI.

If a user gets to the login screen successfully but sees a 403 or a
near-empty page after login, they have no role assigned yet. The fix is
in Keycloak, not in this app.

See :doc:`../deployment/production` for the Keycloak realm configuration
the app expects.

User preferences
================

Each user can personalise certain UI settings. Preferences are stored
per-user (keyed on the Keycloak ``sub`` claim) and persist across sessions
and devices.

Open the **Preferences** page by clicking your username in the bottom-left
corner of the sidebar.

Available settings:

Default taxonomy kingdoms
   Which superkingdom(s) are pre-selected in the taxonomy table when you
   open a sample. Any combination of *Bacteria*, *Viruses*, *Eukaryota*,
   *Archaea*. Default: *Viruses*.

   The kingdom filter on the taxonomy table itself is session-only —
   changing it temporarily does not overwrite your saved preference.

What every user sees
====================

There is no per-case or per-user data partitioning. Every user with any
role sees every case in the database. There are also no field-level
permissions — notes written by one user are visible to every other user.
The audit log (see :doc:`audit-log`) records which user performed each
write.

If your deployment needs per-case access control, that is not currently
supported — talk to the development team.

See also
========

- :doc:`cases-and-samples` — start reviewing cases
- :doc:`taxonomy-browser` — searching and filtering organisms
- :doc:`audit-log` — what the app records about each action
