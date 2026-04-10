===========
User Roles
===========

meta-vis-app has three user roles with different capabilities.

Role overview
=============

.. list-table::
   :header-rows: 1
   :widths: 25, 25, 25, 25

   * - Capability
     - Reader
     - Writer
     - Admin
   * - View cases/samples
     - ✓
     - ✓
     - ✓
   * - View Krona plots
     - ✓
     - ✓
     - ✓
   * - View taxonomy tables
     - ✓
     - ✓
     - ✓
   * - View metaval results
     - ✓
     - ✓
     - ✓
   * - Mark cases reviewed
     - ✗
     - ✓
     - ✓
   * - Add/edit notes
     - ✗
     - ✓
     - ✓
   * - Manage users
     - ✗
     - ✗
     - ✓
   * - Delete cases
     - ✗
     - ✗
     - ✓
   * - Add to ignorelist
     - ✗
     - ✓
     - ✓
   * - Remove from ignorelist
     - ✗
     - ✗
     - ✓

Reader
======

**Best for:** Clinicians reviewing results without modifying data

**Can:**
- View all cases and samples
- See QC metrics and taxonomy tables
- View Krona interactive plots
- View metaval verification results
- Search and filter organisms

**Cannot:**
- Mark cases as reviewed
- Add or edit case notes
- Manage users
- Delete cases
- Modify ignorelist

**Example:** Lab director reviewing results before they're released to clinicians

Writer
======

**Best for:** Clinicians actively reviewing and annotating cases

**Can:**
- Everything a reader can do
- Mark cases as reviewed/unreviewed
- Add and edit case notes
- Add organisms to the outbreak ignorelist
- (Outbreak detection) see Alerts page

**Cannot:**
- Delete cases
- Manage users
- Remove organisms from ignorelist

**Example:** Clinical microbiologist reviewing daily cases, documenting findings

Admin
=====

**Best for:** System administrators, IT staff

**Can:**
- Everything a writer can do
- Manage users (create, delete, change roles)
- Delete cases (and associated blobs from storage)
- Remove organisms from ignorelist
- Access full API

**Cannot:**
- Nothing relevant (admins have full permissions)

**Example:** Lab IT staff or bioinformatics manager

User management
===============

Only admins can manage users. Access the **Admin** panel from the sidebar (visible to admins only).

**Admin panel tasks:**

Creating users
--------------

1. Go to Sidebar → Admin
2. Click "Create User"
3. Enter:
   - Username (unique, alphanumeric)
   - Password (minimum 8 characters)
   - Role (reader, writer, admin)
4. Click Create

Users will log in with their username and password.

Changing user roles
-------------------

1. Go to Sidebar → Admin
2. Find user in the list
3. Click the role dropdown
4. Select new role
5. Confirm

Deleting users
--------------

1. Go to Sidebar → Admin
2. Find user in the list
3. Click Delete
4. Confirm

Deleted users cannot log in. Cases/notes they created remain in the system.

Password management
-------------------

Users should change their password on first login:
1. Log in
2. Click profile icon (top right)
3. Click "Change Password"
4. Enter current password and new password
5. Confirm

**Admins can reset passwords:**
1. Delete the user account
2. Create a new account with the same username
3. Tell user the new temporary password
4. User should change password on first login

Best practices
==============

**For admins:**
- Create accounts in advance of user start date
- Assign least privilege (reader > writer > admin)
- Remove users when they leave
- Regularly review who has admin access
- Enable any monitoring/audit tools your institution has

**For all users:**
- Change password on first login
- Use strong, unique passwords
- Don't share login credentials
- Log out when done
- Report unauthorized access immediately

**For writers:**
- Document observations clearly
- Be specific about findings
- Include confidence levels
- Reference metaval evidence when available
- Follow your institution's reporting standards

User access and data
====================

All users see the same cases and data. There is no per-case or per-user data filtering in meta-vis-app.

**Important implications:**
- All users can see all cases
- No field-level permissions
- All users can see notes from all other users
- Audit trail shows which user created/modified each case

If you need per-case access control (e.g., research user sees only their samples), discuss requirements with the development team.

Getting help
============

If you encounter permission issues:

1. Check your role (click profile → "My Role")
2. Verify you're using a high-enough role for the action
3. Ask an admin if your role needs upgrading
4. Report any permission errors to the IT team

Next steps
==========

- :doc:`cases-and-samples` - Start reviewing cases
- :doc:`taxonomy-browser` - Learn advanced search
- :doc:`administration/user-management` - Admin user management guide
