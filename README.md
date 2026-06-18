![Meta-vis logo](assets/logo.svg)

# Meta-vis

A web application for reviewing the output of clinical metagenomics pipelines.
It ingests results from [nf-core/taxprofiler](https://github.com/nf-core/taxprofiler)
(shotgun metagenomics) and Trana (16S amplicon, Emu), optionally enriched with
[metaval](https://github.com/genomic-medicine-sweden/metaval) read-level
validation. Clinical microbiologists use it to review detections, monitor
contamination and outbreaks, and capture audited case notes.

Full documentation: **https://meta-vis.readthedocs.io/**

## Quick start

Prerequisites: Docker Engine + Compose v2.

```bash
git clone <repo-url>
cd meta-vis-app

cp backend/.env.example  backend/.env       # backend secrets
cp frontend/.env.example frontend/.env      # frontend OIDC config

make keycloak-up                            # local Keycloak on :8081
make up                                     # full dev stack
```

Open <http://localhost:5173> and sign in with `dev-admin` / `dev-admin`.

`make help` lists the rest of the dev targets. The
[local-dev guide](https://meta-vis.readthedocs.io/en/latest/deployment/local-dev.html)
covers configuration, sample ingest, and reset.

## Pre-commit hooks

Run formatters and linters before every commit so CI stays green:

```bash
pip install pre-commit   # or: conda install -c conda-forge pre-commit
pre-commit install
```

`ruff`, `ruff-format`, and `prettier` then run automatically on staged files.
To check the whole repo on demand: `pre-commit run --all-files`.

## Stack

| Layer          | Technology                                              |
|----------------|---------------------------------------------------------|
| Backend        | FastAPI + Motor (async MongoDB), Python 3.13            |
| Database       | MongoDB 7.0                                             |
| Object storage | MinIO / S3-compatible (optional; falls back to MongoDB) |
| Frontend       | React 18 + Vite + Tailwind CSS, TypeScript              |
| Auth           | Keycloak / OIDC (PKCE)                                  |

## License

See `LICENSE` for details.

## Contact

Developed by Genomic Medicine Sweden. For questions or issues, refer to the
[documentation](https://meta-vis.readthedocs.io) or contact the development
team.
