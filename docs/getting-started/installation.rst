================
Installation
================

Prerequisites
=============

Before you begin, ensure you have the following installed:

- `Miniconda <https://docs.conda.io/en/latest/miniconda.html>`_ or Anaconda
- Docker and Docker Compose (for MongoDB and optional MinIO)
- Node.js ≥ 18

Clone the repository
====================

.. code-block:: bash

   git clone <repo-url>
   cd meta-vis-app

Set up the backend
==================

1. **Create the conda environment**

   .. code-block:: bash

      conda env create -f backend/environment.yml
      conda activate meta-vis-app
      pip install -e backend/

2. **Configure environment variables**

   Copy the example and edit with your configuration:

   .. code-block:: bash

      cp backend/.env.example backend/.env

   Edit ``backend/.env`` to match your setup. At minimum:

   .. code-block:: ini

      MONGODB_HOST=localhost
      MONGODB_PORT=27017
      MONGODB_DB_NAME=meta-vis-dev
      MONGODB_USERNAME=meta_vis_app
      MONGODB_PASSWORD=<choose-a-password>
      MONGO_ROOT_PASSWORD=<choose-a-root-password>
      MONGODB_AUTH_SOURCE=admin

      APP_ENV=development
      LOG_LEVEL=info

      JWT_SECRET=<choose-a-long-random-string>

3. **Start Docker services**

   .. code-block:: bash

      cd backend
      docker compose up -d

   This starts MongoDB. If the container already exists, remove the volume first:

   .. code-block:: bash

      docker compose down -v
      docker compose up -d

4. **Create the first user**

   .. code-block:: bash

      cd backend
      conda activate meta-vis-app
      python create_user.py --username admin --password yourpassword --role admin

   Available roles: ``reader``, ``writer``, ``admin``

5. **Start the backend**

   .. code-block:: bash

      cd backend
      conda activate meta-vis-app
      uvicorn app.main:app --reload --host 127.0.0.1

   The API will be available at ``http://localhost:8000`` with interactive docs at ``http://localhost:8000/docs``.

Set up the frontend
===================

.. code-block:: bash

   cd frontend
   npm install
   npm run dev

The app will be available at ``http://localhost:5173``.

Log in with the credentials you created in step 4.

Optional: Object storage
=========================

By default, Krona HTML files and IGV reports are stored in MongoDB. For production deployments, it's recommended to use MinIO or S3-compatible storage.

See :doc:`../deployment/object-storage` for configuration details.

Optional: Taxonomy reference data
==================================

The app uses reference taxonomy data for detailed organism information. Load it with:

.. code-block:: bash

   cd backend
   conda activate meta-vis-app
   python load_taxonomy.py

This downloads NCBI taxonomy data (~110 MB) and populates the database. See :doc:`../administration/taxonomy-reference` for scheduling regular updates.

Verification
============

To verify the installation is working:

1. Frontend loads at ``http://localhost:5173``
2. You can log in with your admin credentials
3. Backend API docs available at ``http://localhost:8000/docs``

If you encounter issues, see :doc:`../administration/troubleshooting`.

Next steps
==========

- :doc:`quick-start` - Load some sample data and explore
- :doc:`../administration/ingestion` - Learn how to ingest real data
