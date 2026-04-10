================
Object Storage
================

Krona HTML files and IGV reports are large (1–2 MB each). The app supports two backends for storing these blobs: MongoDB (default) or S3-compatible storage.

MongoDB backend (default)
==========================

When no object storage is configured, blobs are stored in MongoDB's ``blobs`` collection.

**Advantages:**
- Zero additional setup
- Works out of the box
- No external dependencies

**Disadvantages:**
- Increases MongoDB working set
- Not recommended for large deployments

**Best for:** Development, small deployments (<100 cases)

MinIO / S3 backend
==================

Store blobs in S3-compatible object storage, keeping MongoDB lean and fast.

Enabling MinIO (included with docker-compose)
==============================================

1. Uncomment the storage variables in ``backend/.env``:

   .. code-block:: ini

      OBJECT_STORAGE_ENDPOINT=http://localhost:9000
      OBJECT_STORAGE_ACCESS_KEY=minioadmin
      OBJECT_STORAGE_SECRET_KEY=minioadmin
      OBJECT_STORAGE_BUCKET=meta-vis

2. Start MinIO:

   .. code-block:: bash

      cd backend
      docker compose up -d minio

3. Restart the backend - it auto-detects the env vars and switches to S3 backend

MinIO console is available at ``http://localhost:9001`` with the same credentials.

Using AWS S3 or other S3-compatible services
=============================================

Set environment variables to your S3 provider:

.. code-block:: ini

   OBJECT_STORAGE_ENDPOINT=https://s3.amazonaws.com
   OBJECT_STORAGE_ACCESS_KEY=<your-access-key>
   OBJECT_STORAGE_SECRET_KEY=<your-secret-key>
   OBJECT_STORAGE_BUCKET=<your-bucket-name>

No code changes required - the app auto-detects the endpoint and switches to S3 mode.

**AWS S3 notes:**
- Create an IAM user with S3 permissions
- Use the user's access key and secret
- Create a bucket beforehand
- Ensure the bucket region matches your configuration

Blob storage key structure
==========================

Files are organized with hierarchical keys:

.. code-block:: text

   meta-vis/
     krona/{case_object_id}/{classifier}.html
     igv/{case_object_id}/{sample_name}/{classifier}/{organism_name}.html

**Example:**
- Krona: ``meta-vis/krona/507f1f77bcf86cd799439011/kraken2.html``
- IGV: ``meta-vis/igv/507f1f77bcf86cd799439011/SRR13439790/centrifuge/Escherichia-phage-ECBP1.html``

Switching backends
==================

Cases ingested with one backend have blobs only in that backend. Switching backends requires:

1. Delete the case via the UI or API (removes blobs from old backend)
2. Re-ingest the case

For large migrations, consider:
- Backing up MongoDB before deletion
- Running ingest in batches
- Monitoring storage usage during transition

If you have many cases, contact the development team for migration tools.

Backup and recovery
===================

**MongoDB blob backend:**
  Blobs are in the MongoDB ``blobs`` collection. Include in standard MongoDB backups.

**S3 backend:**
  Use your S3 provider's backup features:
  - MinIO: Version objects, set replication
  - AWS S3: Enable versioning, cross-region replication, or backup services

Best practices
==============

- **Development:** Use MongoDB backend (simplest)
- **Production:** Use S3 backend for scalability
- **Backup:** Test restore procedures regularly
- **Monitoring:** Monitor storage usage and costs
- **Retention:** Implement policies for old blob cleanup if needed

Next steps
==========

- :doc:`environment` - Configure environment variables
- :doc:`production` - Production deployment considerations
