# Future Optimisations

## Lean taxonomic profiles

### Background

Each sample document in the `samples` collection contains one or more
`ClassifierProfile` objects. Each profile holds a `profile` array of taxon
entries, where every entry currently stores:

```
{
"taxon_id": 11520,
"name": "Influenza A virus",
"rank": "species",
"abundance": 312.0,
"superkingdom": "Viruses"
}
```

At the current scale this is fine. At the expected ceiling of ~200k samples
with ~800 taxa per sample per classifier and 3 classifiers, the `profiles`
arrays account for an estimated 30–50 GB of the `samples` collection.
The fields `name`, `rank`, and `superkingdom` are properties of the taxon
itself — not the observation — and are duplicated across every sample that
detects a given taxon.

### The migration

Once the `taxa` collection (introduced alongside `load_taxonomy.py`) is
well-populated, profile entries can be slimmed to:

```
{
"taxon_id": 11520,
"abundance": 312.0
}
```

This removes `name`, `rank`, and `superkingdom` from every embedded entry,
reducing estimated profile storage by 40–50%. At 200k samples this saves
roughly 15–25 GB, which meaningfully increases the fraction of the working
set that MongoDB can hold in RAM.

### What must be in place first

- The `taxa` collection must be fully populated via `load_taxonomy.py` and
  kept current via its scheduled refresh.
- The ingest-time fallback upsert in `orchestrator.py` must have been
  running long enough that all observed taxon IDs have entries in `taxa`.
- All API endpoints that return profile data must hydrate `name`, `rank`,
  and `superkingdom` from a batch `taxa` lookup rather than reading them
  from the profile entries directly.

### Migration approach

1. Run `load_taxonomy.py` and verify `taxa` coverage.
2. Update all profile-returning API endpoints to do batch `taxa` lookups
   (a single `db["taxa"].find({"taxon_id": {"$in": [...ids]}})` per request).
3. Deploy the updated API.
4. Run a one-off migration script that strips `name`, `rank`,
   `superkingdom` from all `profiles.profile[]` entries in `samples`.
5. Remove the now-redundant fields from `TaxonEntry` in `models/sample.py`.

### Caveat: do not apply to `outbreak_taxa`

The pre-computed `outbreak_taxa` array on each sample document should
**not** be slimmed — it is small and already filtered, and the outbreak
aggregation pipeline reads `name` directly from it to avoid a join.