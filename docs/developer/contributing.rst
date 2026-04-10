============
Contributing
============

Guide for developers contributing to meta-vis-app.

Development setup
=================

**Clone the repository:**

.. code-block:: bash

   git clone <repo-url>
   cd meta-vis-app

**Set up backend:**

.. code-block:: bash

   cd backend
   conda env create -f environment.yml
   conda activate meta-vis-app
   pip install -e ".[dev]"
   cp .env.example .env
   docker compose up -d

**Set up frontend:**

.. code-block:: bash

   cd frontend
   npm install

**Start development servers:**

Backend:

.. code-block:: bash

   cd backend
   uvicorn app.main:app --reload

Frontend:

.. code-block:: bash

   cd frontend
   npm run dev

Code style
==========

**Backend (Python):**

Uses ruff and mypy for linting and type checking.

.. code-block:: bash

   # Format code
   ruff format .
   
   # Check linting
   ruff check .
   
   # Type checking
   mypy app/

All code must pass:

.. code-block:: bash

   cd backend
   ruff check .
   ruff format --check .
   mypy app/

**Frontend (JavaScript):**

Uses Prettier and ESLint.

.. code-block:: bash

   # Format code
   npm run format
   
   # Check linting
   npm run lint

All code must pass:

.. code-block:: bash

   cd frontend
   npm run format --check
   npm run lint

**Type hints:**

All Python functions must be properly type-hinted:

.. code-block:: python

   # Good
   async def get_case(case_id: str) -> CaseDetail:
       """Get case details by ID."""
       ...
   
   # Bad - missing return type
   async def get_case(case_id: str):
       ...

**JSDoc comments:**

Use JSDoc for complex functions:

.. code-block:: javascript

   /**
    * Fetch cases with optional filtering
    * @param {Object} filters - Filter criteria
    * @param {string} filters.status - "reviewed" or "unreviewed"
    * @returns {Promise<Array<Case>>} Array of cases
    */
   async function getCases(filters = {}) { ... }

Testing
=======

**Running tests:**

.. code-block:: bash

   cd backend
   pytest tests/                    # All tests
   pytest tests/unit/               # Unit tests only
   pytest tests/integration/        # Integration tests only
   pytest -v                        # Verbose output
   pytest --cov                     # Coverage report

**Writing unit tests:**

.. code-block:: python

   # tests/unit/test_my_feature.py
   import pytest
   from app.module import function_to_test

   def test_function_returns_correct_value():
       result = function_to_test("input")
       assert result == "expected"

   def test_function_handles_error():
       with pytest.raises(ValueError):
           function_to_test(None)

**Writing integration tests:**

.. code-block:: python

   # tests/integration/test_my_endpoint.py
   import pytest
   from httpx import AsyncClient

   @pytest.mark.asyncio
   async def test_get_cases(client: AsyncClient, db_with_cases):
       response = await client.get("/api/cases")
       assert response.status_code == 200
       assert len(response.json()) > 0

**Test coverage:**

Aim for > 80% coverage on new code:

.. code-block:: bash

   pytest --cov=app --cov-report=html
   # Open htmlcov/index.html to see coverage

Commit messages
===============

Use conventional commits:

.. code-block:: text

   feat: Add outbreak alert caching
   fix: Correct taxonomy lineage query
   docs: Update installation guide
   refactor: Simplify blob storage abstraction
   test: Add integration tests for metaval
   chore: Update dependencies

Format:

.. code-block:: text

   <type>(<scope>): <subject>
   
   <body>
   
   <footer>

**Types:**
- **feat** - New feature
- **fix** - Bug fix
- **docs** - Documentation
- **refactor** - Code refactoring without feature change
- **test** - Adding or updating tests
- **chore** - Maintenance, dependency updates
- **perf** - Performance improvement

**Scope** (optional):
- Component or module affected (e.g., "outbreak", "ingestor", "api")

**Subject:**
- Imperative mood ("add" not "added")
- No period at end
- < 50 characters

**Body** (optional):
- Explain what and why
- Wrap at 72 characters
- Reference issues: "Fixes #123"

Pull request workflow
=====================

1. **Create a branch:**

   .. code-block:: bash

      git checkout -b feature/my-feature

2. **Make changes:**
   - Write code
   - Add tests
   - Update documentation
   - Format code with ruff/prettier
   - Verify tests pass

3. **Commit with good messages:**

   .. code-block:: bash

      git commit -m "feat(outbreak): Add time window customization"

4. **Push and create PR:**

   .. code-block:: bash

      git push origin feature/my-feature

5. **PR checks must pass:**
   - Linting (ruff, eslint)
   - Type checking (mypy)
   - All tests passing
   - Coverage maintained or improved

6. **Code review:**
   - Address feedback
   - Update commits with new changes
   - Don't force-push after review started

7. **Merge:**
   - Squash or rebase as appropriate
   - Delete branch after merge

API development
===============

**Adding a new endpoint:**

1. Define Pydantic models in ``app/models/``:

   .. code-block:: python

      from pydantic import BaseModel
      
      class MyResponse(BaseModel):
          """Response model."""
          id: str
          name: str

2. Create router in ``app/routers/``:

   .. code-block:: python

      from fastapi import APIRouter, HTTPException
      from typing import List
      
      router = APIRouter(prefix="/api/my", tags=["my"])
      
      @router.get("/endpoint", response_model=List[MyResponse])
      async def get_endpoint(param: str) -> List[MyResponse]:
          """Get endpoint description."""
          if not param:
              raise HTTPException(status_code=400, detail="Invalid param")
          return [MyResponse(id="1", name="Test")]

3. Register router in ``app/main.py``:

   .. code-block:: python

      from app.routers import my
      
      app.include_router(my.router)

4. Test the endpoint:

   .. code-block:: bash

      curl http://localhost:8000/api/my/endpoint?param=test

Frontend development
====================

**Component structure:**

.. code-block:: javascript

   // src/pages/MyPage.jsx
   import { useState, useEffect } from 'react';
   import { getMyData } from '../api/myapi';

   export default function MyPage() {
     const [data, setData] = useState(null);
     const [loading, setLoading] = useState(true);

     useEffect(() => {
       async function load() {
         try {
           const result = await getMyData();
           setData(result);
         } finally {
           setLoading(false);
         }
       }
       load();
     }, []);

     if (loading) return <div>Loading...</div>;
     if (!data) return <div>No data</div>;

     return <div>{/* Render data */}</div>;
   }

**Using Tailwind CSS:**

.. code-block:: javascript

   <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
     <div className="bg-white rounded-lg shadow p-6">
       <h3 className="text-lg font-semibold mb-2">Card Title</h3>
       <p className="text-gray-600">Card content</p>
     </div>
   </div>

**API client functions:**

.. code-block:: javascript

   // src/api/myapi.js
   import { client } from './client';

   export async function getMyData(filters = {}) {
     const response = await client.get('/api/my/data', { params: filters });
     return response.data;
   }

   export async function createMyData(payload) {
     const response = await client.post('/api/my/data', payload);
     return response.data;
   }

Database development
====================

**Adding a new collection:**

1. Define document structure in documentation
2. Create indexes if needed:

   .. code-block:: python

      # In app/database.py or migration script
      db.new_collection.create_index([("key_field", pymongo.ASCENDING)])

3. Add Pydantic model for validation
4. Create repository functions for CRUD operations
5. Write tests for database operations

**Migrations:**

Currently, meta-vis-app doesn't have formal migrations. For schema changes:

1. Document the change clearly
2. Create a one-time script in ``backend/scripts/``
3. Test thoroughly on development database
4. Run on staging first
5. Schedule downtime if needed for production

Performance optimization
=========================

**Before optimizing:**

1. Measure the actual problem (profile, benchmark)
2. Identify the bottleneck (database, computation, I/O)
3. Test your fix (before/after benchmarks)

**Common optimizations:**

**Database:**
- Add indexes on frequently queried fields
- Batch operations (bulk_write instead of insert one-by-one)
- Use projection to fetch only needed fields

**Backend:**
- Cache expensive computations
- Use async/await for I/O
- Batch API responses with pagination

**Frontend:**
- Use React.memo for expensive components
- Implement pagination for large lists
- Cache API responses (TanStack Query, etc.)

Documentation
==============

**Code comments:**

Write comments for "why", not "what":

.. code-block:: python

   # Bad - explains what the code does
   # Add the values
   total = sum(values)
   
   # Good - explains why
   # Use sum() to efficiently compute total abundance for sorting
   total = sum(values)

**Docstrings:**

All public functions need docstrings:

.. code-block:: python

   async def ingest_case(case_id: str, data: dict) -> CaseDetail:
       """
       Ingest a new case into the database.
       
       Args:
           case_id: Unique case identifier
           data: Case data including samples and classifiers
       
       Returns:
           CaseDetail with created case information
       
       Raises:
           ValueError: If case_id is already in use
           ValidationError: If data doesn't match expected schema
       """

**README files:**

Each major component should have a README:

.. code-block:: markdown

   # Outbreak Detection Module
   
   Monitors viral taxa across cases for early outbreak detection.
   
   ## How it works
   ...
   
   ## API
   ...
   
   ## Performance
   ...

Release process
===============

**Versioning:**

Uses semantic versioning: MAJOR.MINOR.PATCH

- **MAJOR** - Incompatible changes (breaking API)
- **MINOR** - New features (backwards compatible)
- **PATCH** - Bug fixes

**Release steps:**

1. Update version in ``pyproject.toml`` and ``package.json``
2. Update ``CHANGELOG.md``
3. Commit: ``chore: Release v0.2.0``
4. Tag: ``git tag v0.2.0``
5. Push: ``git push origin main --tags``
6. Build artifacts: Docker image, etc.

Debugging tips
==============

**Backend debugging:**

.. code-block:: python

   # Add debugging to code
   import logging
   logger = logging.getLogger(__name__)
   
   logger.debug(f"Processing case: {case_id}")
   logger.warning(f"Unexpected result: {result}")

**View logs:**

.. code-block:: bash

   docker logs -f meta-vis-app
   journalctl -u meta-vis-app -f

**Use debugger:**

.. code-block:: python

   import pdb; pdb.set_trace()  # Breakpoint
   # Or use VSCode debugger

**Frontend debugging:**

- Browser DevTools: F12
- Console: F12 → Console
- Network tab: F12 → Network
- React DevTools extension

Getting help
============

- **Code questions** - Ask in PR comments
- **Architecture questions** - Check docs first, then ask
- **Bug reports** - Create GitHub issue with minimal reproduction
- **Feature requests** - Discuss in issues before implementing

Next steps
==========

- :doc:`architecture` - System design
- :doc:`data-model` - Data structures
- :doc:`performance` - Performance tuning
