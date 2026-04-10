================
Troubleshooting
================

Common issues and how to resolve them.

Application won't start
=======================

**Backend won't start**

Check:
1. MongoDB is running: ``docker ps | grep mongodb``
2. Environment variables are set correctly: ``echo $MONGODB_HOST``
3. Port 8000 is available: ``lsof -i :8000``
4. Dependencies installed: ``pip list | grep fastapi``

If ``ConnectionRefusedError``:
- Start MongoDB: ``docker compose up -d``
- Or check MongoDB logs: ``docker logs mongodb``

If ``AuthenticationFailed``:
- Check ``.env`` credentials match ``mongo-init.js``
- Reset database: ``docker compose down -v && docker compose up -d``

**Frontend won't start**

Check:
1. Node.js is installed: ``node --version``
2. Dependencies installed: ``npm list``
3. Port 5173 is available: ``lsof -i :5173``

If ``Module not found``:
- Reinstall dependencies: ``npm install``

If ``ENOSPC`` (no space on disk):
- Check disk usage: ``df -h``
- Clean node cache: ``npm cache clean --force``

Can't log in
============

**"Invalid credentials"**

1. Check username is correct (case-sensitive)
2. Check password is correct
3. Verify account exists: contact admin
4. Try password reset (admin only)

**"User not found"**

1. Account might have been deleted
2. Check spelling of username
3. Contact admin to recreate account

**"Connection refused"**

1. Backend isn't running: ``curl http://localhost:8000/docs``
2. Backend on wrong port: check ``.env``
3. Network issue: check firewall rules

Frontend slow or unresponsive
=============================

**Page load is slow**

1. Check browser network tab (F12 → Network)
2. Identify slow API call
3. Check backend logs for slow queries
4. Restart backend: ``uvicorn app.main:app --reload``

**Taxonomy table takes forever to load**

1. Sample might have very many organisms (> 50,000)
2. Use search/filters to narrow results
3. Switch to a different classifier
4. Contact admin if persistent

**UI buttons don't respond**

1. Check browser console (F12 → Console) for errors
2. Try refreshing the page
3. Try a different browser
4. Clear browser cache: Ctrl+Shift+Delete

Case or sample won't load
=========================

**"Case not found" error**

1. Case ID might be wrong
2. Case might have been deleted
3. Try refreshing: F5
4. Check URL is correct

**Blank page after clicking case**

1. Check browser console (F12 → Console) for errors
2. Try refreshing
3. Check that metaval data (if expected) is present
4. Check backend logs for errors

**Krona plot is blank or won't render**

1. Krona HTML upload might have failed during ingest
2. Check object storage configuration
3. Try downloading and opening Krona HTML directly
4. Re-ingest the case if data is corrupted

Ingest fails
============

**"File not found"**

1. Paths must be absolute: ``/data/case/...`` not ``./data/...``
2. Check file exists: ``ls -la /path/to/file``
3. Check permissions: ``ls -la /path/to/file`` should be readable

**"Column not found in taxpasta"**

1. Check exact column names in TSV: ``head multiqc_data.json``
2. Column names are case-sensitive
3. Check database suffixes match (e.g., ``k2_pluspf``, ``p_compressed+h+v``)

**"Case already exists"**

1. Delete existing case via Admin panel
2. Or choose a different case_id
3. Re-run ingest

**"Connection refused"**

1. MongoDB isn't running: ``docker ps``
2. Start it: ``docker compose up -d``
3. Check MONGODB_HOST in ``.env``

**"Authentication failed"**

1. Check username/password in ingest command
2. User must have writer or admin role
3. Try creating user again: ``python create_user.py --username ...``

**"Krona upload failed"**

1. Object storage not configured or down
2. If using MinIO, check it's running: ``docker ps | grep minio``
3. Check OBJECT_STORAGE_* variables in ``.env``
4. Check free disk space: ``df -h``

Database issues
===============

**"Disk space full"**

1. Check disk usage: ``df -h``
2. Free up space or add storage
3. Restart MongoDB: ``docker compose restart mongodb``

**"Connection timeout"**

1. MongoDB might be hung
2. Restart: ``docker compose restart mongodb``
3. Check logs: ``docker logs mongodb``

**"Out of memory"**

1. MongoDB running on small server
2. Check available RAM: ``free -h``
3. Upgrade MongoDB resource limits
4. Archive old cases to separate database

**"No space left on device"**

1. Check volume mounts: ``docker inspect meta-vis-app | grep Mounts``
2. Check MongoDB volume: ``docker volume ls``
3. Increase volume size or add new volume
4. Remove old Krona/IGV files if not needed

Object storage issues
====================

**"Connection refused" to S3**

1. Check OBJECT_STORAGE_ENDPOINT is correct
2. For MinIO, check it's running: ``docker ps``
3. Try connecting manually: ``aws s3 ls`` (if using AWS)
4. Check security groups/firewall rules

**"Access denied" to S3 bucket**

1. Check credentials in ``.env``
2. Check IAM permissions (AWS)
3. Check bucket ownership
4. Try uploading test file manually

**"Bucket doesn't exist"**

1. App auto-creates bucket on first ingest
2. If it doesn't, create manually (MinIO console or AWS)
3. Check OBJECT_STORAGE_BUCKET in ``.env``

Metaval integration issues
=========================

**IGV files missing from results**

1. Check ``--metaval-igv`` path was provided during ingest
2. Check directory structure:
   - ``metaval/igv/`` must exist as subdirectory
   - ``metaval/blast/`` and ``metaval/extracted_reads/`` must be present
3. Check blobs were uploaded (check object storage)
4. Re-ingest if necessary

**BLAST results show "not available"**

1. metaval might not have tested that organism
2. Organism might be below metaval thresholds
3. Check metaval output directory
4. Consult metaval documentation

Outbreak alerts not working
===========================

**No alerts appearing**

1. Make sure cases have order_date set
2. Check time window (7/14/30 days)
3. Might not have any viral taxa in 2+ cases
4. Check outbreak ignorelist (might be excluding all)

**Alerts disappear after refresh**

1. This is normal if they fall outside the time window
2. Or if new ingestions changed the time range
3. Try wider time window (30 days)

**Can't add to ignorelist**

1. Must be writer or admin
2. Try as admin first
3. Check browser console for errors

Performance problems
====================

**API calls are slow**

1. Check MongoDB query performance: ``db.currentOp()``
2. Look for missing indexes
3. Check server resources (CPU, RAM, disk)
4. Increase backend workers: ``uvicorn ... --workers 8``

**Large cases take too long to ingest**

1. Normal for 100+ samples or 1000+ organisms
2. Can take 10-30 minutes for very large cases
3. Run overnight: ``nohup python ingest.py ... &``
4. Monitor progress: ``docker logs -f meta-vis-app``

**Database grows too large**

1. Archive old cases (export and delete)
2. Consider splitting into separate database
3. Check blob storage isn't bloating database
4. Ensure object storage is being used for Krona/IGV

Getting help
============

**Gather information before asking for help:**

1. What were you trying to do?
2. What error message did you see?
3. Check relevant logs:
   - Backend: ``docker logs meta-vis-app``
   - MongoDB: ``docker logs mongodb``
   - Frontend: Browser console (F12 → Console)
4. Include command you ran (with sensitive paths redacted)
5. Include your OS and software versions

**Finding logs:**

.. code-block:: bash

   # Backend logs
   docker logs -f meta-vis-app
   
   # MongoDB logs
   docker logs -f mongodb
   
   # journalctl (if using systemd)
   journalctl -u meta-vis-app -f
   
   # Application logs in python
   tail -f /path/to/ingest.log

**Debug mode:**

Set ``LOG_LEVEL=debug`` in ``.env`` for verbose output:

.. code-block:: bash

   LOG_LEVEL=debug
   docker compose restart meta-vis-app

**Check dependencies:**

.. code-block:: bash

   # Python packages
   pip list | grep fastapi
   
   # Node packages
   npm list react
   
   # System services
   docker ps
   docker ps -a  # includes stopped containers

Next steps
==========

If you can't resolve the issue:

1. Gather the information above
2. Check recent code changes
3. Check if updates are available
4. Contact the development team with details
