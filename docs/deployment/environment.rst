======================
Environment Variables
======================

meta-vis-app configuration is managed through environment variables in ``backend/.env``.

Getting started
===============

Copy the example file:

.. code-block:: bash

   cp backend/.env.example backend/.env

Then edit ``backend/.env`` with your settings.

MongoDB configuration
=====================

.. code-block:: ini

   MONGODB_HOST=localhost
   MONGODB_PORT=27017
   MONGODB_DB_NAME=meta-vis-dev
   MONGODB_USERNAME=meta_vis_app
   MONGO_APP_PASSWORD=<strong-password>
   MONGO_ROOT_PASSWORD=<strong-root-password>
   MONGODB_AUTH_SOURCE=admin

- **MONGODB_HOST** - MongoDB server hostname or IP
- **MONGODB_PORT** - MongoDB server port
- **MONGODB_DB_NAME** - Database name to use
- **MONGODB_USERNAME** - App user (created by ``mongo-init.js``)
- **MONGO_APP_PASSWORD** - Password for app user
- **MONGO_ROOT_PASSWORD** - Root password for admin access
- **MONGODB_AUTH_SOURCE** - Authentication database (usually ``admin``)

Application configuration
==========================

.. code-block:: ini

   APP_ENV=development
   LOG_LEVEL=info

- **APP_ENV** - Either ``development`` or ``production``
- **LOG_LEVEL** - One of ``debug``, ``info``, ``warning``, ``error``, ``critical``

Security
========

.. code-block:: ini

   JWT_SECRET=<very-long-random-string>

- **JWT_SECRET** - Secret key for JWT token signing. Must be a long, random string. Generate with:

  .. code-block:: bash

     python -c "import secrets; print(secrets.token_urlsafe(32))"

Object storage (optional)
==========================

Only configure if you want to use S3-compatible storage instead of MongoDB for blobs.

.. code-block:: ini

   OBJECT_STORAGE_ENDPOINT=http://localhost:9000
   OBJECT_STORAGE_ACCESS_KEY=minioadmin
   OBJECT_STORAGE_SECRET_KEY=minioadmin
   OBJECT_STORAGE_BUCKET=meta-vis

- **OBJECT_STORAGE_ENDPOINT** - S3 service endpoint (MinIO, AWS S3, etc.)
- **OBJECT_STORAGE_ACCESS_KEY** - Access key ID
- **OBJECT_STORAGE_SECRET_KEY** - Secret access key
- **OBJECT_STORAGE_BUCKET** - Bucket name to store blobs in

For AWS S3:

.. code-block:: ini

   OBJECT_STORAGE_ENDPOINT=https://s3.amazonaws.com
   OBJECT_STORAGE_ACCESS_KEY=<your-access-key>
   OBJECT_STORAGE_SECRET_KEY=<your-secret-key>
   OBJECT_STORAGE_BUCKET=<your-bucket-name>

See :doc:`object-storage` for details.

Example configuration
=====================

Development setup:

.. code-block:: ini

   MONGODB_HOST=localhost
   MONGODB_PORT=27017
   MONGODB_DB_NAME=meta-vis-dev
   MONGODB_USERNAME=meta_vis_app
   MONGO_APP_PASSWORD=devpassword123
   MONGO_ROOT_PASSWORD=rootpassword456
   MONGODB_AUTH_SOURCE=admin

   APP_ENV=development
   LOG_LEVEL=debug

   JWT_SECRET=super-secret-jwt-key-change-in-production

Production setup (with S3):

.. code-block:: ini

   MONGODB_HOST=mongodb.prod.internal
   MONGODB_PORT=27017
   MONGODB_DB_NAME=meta-vis-prod
   MONGODB_USERNAME=meta_vis_app
   MONGO_APP_PASSWORD=<strong-password>
   MONGO_ROOT_PASSWORD=<strong-password>
   MONGODB_AUTH_SOURCE=admin

   APP_ENV=production
   LOG_LEVEL=warning

   JWT_SECRET=<very-long-random-string>

   OBJECT_STORAGE_ENDPOINT=https://s3.amazonaws.com
   OBJECT_STORAGE_ACCESS_KEY=<access-key>
   OBJECT_STORAGE_SECRET_KEY=<secret-key>
   OBJECT_STORAGE_BUCKET=meta-vis-prod

Best practices
==============

1. **Never commit ``.env`` to version control** - It contains secrets
2. **Use strong passwords** - Especially for production
3. **Rotate JWT_SECRET regularly** - Invalidates all existing tokens
4. **Use environment-specific .env files** - ``.env.dev``, ``.env.prod``, etc.
5. **Use a secrets management system** - In production, use Docker secrets, Kubernetes secrets, or a dedicated secrets manager

Next steps
==========

- :doc:`docker-compose` - Manage services
- :doc:`object-storage` - Configure external storage
- :doc:`production` - Production deployment
