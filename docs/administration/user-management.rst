==================
User Management
==================

Administering user accounts and access control.

Creating the first user
=======================

The first user must be created via command line:

.. code-block:: bash

   cd backend
   conda activate meta-vis-app
   python create_user.py --username admin --password yourpassword --role admin

Once created, admins can add more users via the Admin panel.

Using create_user.py
====================

.. code-block:: bash

   python create_user.py \
     --username <username> \
     --password <password> \
     --role <role>

**Arguments:**

- **--username** - Alphanumeric, unique. Used for login.
- **--password** - Minimum 8 characters. Should be strong.
- **--role** - One of: ``reader``, ``writer``, ``admin``

**Example:**

.. code-block:: bash

   python create_user.py --username analyst1 --password Tr0pic@l$unset --role writer

**Output:**

.. code-block:: text

   ✓ User 'analyst1' created with role 'writer'

User management via Admin panel
===============================

Only admins can see the Admin panel. Access via Sidebar → Admin.

**Users list:**
- Shows all users
- Username and role visible
- Options to change role or delete user

**Creating users:**

1. Click "Create User"
2. Enter:
   - Username (unique, alphanumeric)
   - Password (minimum 8 characters)
   - Role (reader, writer, admin)
3. Click Create
4. User can log in immediately

**Changing roles:**

1. Find user in list
2. Click role dropdown
3. Select new role
4. Confirm
5. Changes take effect immediately

**Deleting users:**

1. Find user in list
2. Click Delete
3. Confirm

Deleted users:
- Cannot log in
- Data they created remains (with their username)
- Can be recreated with same username later

Best practices
==============

**For security:**

1. **Strong passwords** - Enforce 12+ characters, mixed case, numbers, symbols
2. **Unique usernames** - No shared accounts
3. **Principle of least privilege** - Use lowest role needed
4. **Regular audits** - Review users quarterly
5. **Remove promptly** - Delete accounts when users leave

**For usability:**

1. **Clear usernames** - Use first.last or similar
2. **Onboard properly** - Walk through initial login
3. **Change password first** - Users should change temp passwords on first login
4. **Document roles** - Make clear what each person's role is

**For accountability:**

1. **Audit trail** - Note shows who created/modified it
2. **Track admins** - Keep list of who has admin access
3. **Document decisions** - Why was someone an admin?
4. **Regular review** - Check admin list quarterly

User roles reference
====================

See :doc:`../user-guide/user-roles` for detailed capability matrix.

**Quick reference:**

- **Reader** - View only
- **Writer** - Reviewers (view + mark reviewed + add notes + ignorelist)
- **Admin** - System admins (everything + user management + delete cases)

Password management
===================

**Resetting passwords:**

1. Delete the user account
2. Create a new account with same username and temporary password
3. Tell user to change password on first login

**User password change:**

1. Log in to meta-vis-app
2. Click profile icon (top right)
3. Click "Change Password"
4. Enter current password and new password
5. Confirm

Account access troubleshooting
==============================

**User can't log in**

Check:
1. Username is correct (case-sensitive)
2. Password is correct
3. Account hasn't been deleted
4. No login attempt rate limiting (recheck in 5 minutes)

**User account is locked**

- Not currently implemented (no lockout after failed attempts)
- User can retry immediately

**User has wrong permissions**

Check:
1. Go to Admin panel
2. Verify user's role
3. Change if needed
4. User might need to log out and back in to see changes

**Audit trail for user actions**

Currently, meta-vis-app doesn't have detailed audit logging. To add:
1. Request feature from development team
2. Or implement custom logging middleware
3. Or use external audit tools (CloudTrail, etc.)

Best practice recommendations
=============================

**Small deployment (< 10 users):**

.. code-block:: text

   Role assignments:
   - 1–2 admins (IT staff)
   - 3–5 writers (clinicians)
   - Rest as readers (clinicians who only review)

**Medium deployment (10–50 users):**

.. code-block:: text

   Role assignments:
   - 1–2 admins (IT staff)
   - 5–10 writers (senior clinicians/reviewers)
   - Rest as readers (junior clinicians)
   
   Consider:
   - Department-level grouping
   - Training program for writers
   - Quarterly role reviews

**Large deployment (50+ users):**

.. code-block:: text

   Consider:
   - Integration with institutional directory (LDAP/Active Directory)
   - Request from development team
   - Single sign-on (SSO)
   - Department-specific access controls
   - Formal audit logging

Integration with institutional directory
========================================

Currently, meta-vis-app uses local username/password authentication.

**To integrate with institutional LDAP/Active Directory:**

1. Contact development team
2. Provide:
   - LDAP server details
   - User attribute mappings
   - Role mapping strategy
3. Implement custom authentication middleware

This would enable:
- Single sign-on
- Centralized user management
- Automatic role synchronization
- Audit trail from institution

Next steps
==========

- :doc:`../user-guide/user-roles` - Understand user roles
- :doc:`ingestion` - Manage ingest user accounts
- Contact development team for advanced features (SSO, audit logging)
