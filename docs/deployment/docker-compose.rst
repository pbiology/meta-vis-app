=================
Docker Compose
=================

meta-vis-app includes a ``docker-compose.yml`` that orchestrates MongoDB and optional MinIO services.

Starting services
=================

.. code-block:: bash

   cd backend
   docker compose up -d

This starts:

- **MongoDB** on ``localhost:27017``
- **MinIO** (optional, if enabled in ``.env``) on ``localhost:9000``
- **MinIO Console** on ``localhost:9001`` (optional)

Stopping services
=================

.. code-block:: bash

   cd backend
   docker compose down

To also remove volumes (data will be lost):

.. code-block:: bash

   cd backend
   docker compose down -v

Viewing logs
============

View all services:

.. code-block:: bash

   docker compose logs -f

View a specific service:

.. code-block:: bash

   docker compose logs -f mongodb

Resetting the database
======================

To clear all data and start fresh:

.. code-block:: bash

   cd backend
   docker compose down -v
   docker compose up -d

The MongoDB initialization script (``mongo-init.js``) runs automatically on first start, creating the application database user.

Next steps
==========

- :doc:`environment` - Configure environment variables
- :doc:`object-storage` - Set up S3 storage (optional)
- :doc:`production` - Production deployment considerations
