# app/taxon_lists/__init__.py
"""Curated lists of NCBI taxon IDs (ignorelists, known pathogens, contaminants).

Split so the rules can be unit-tested without a database:

- ``kinds``   — which kinds of list exist and what each kind allows. Pure.
- ``rules``   — entry validation against a kind. Pure.
- ``store``   — MongoDB access for ``taxon_lists`` / ``taxon_list_entries``.
- ``service`` — one write end to end: validate, persist, invalidate, audit.
"""
