# app/constants.py

# NCBI taxon IDs that represent root, unclassified, or host entries.
# These are structural nodes in the taxonomy tree, not real organisms,
# and should be excluded from any biological signal analysis.
#
#   0        — unclassified / no hit
#   1        — root
#   131567   — cellular organisms (super-root grouping node)
#   9606     — Homo sapiens
HOST_TAXON_IDS: frozenset[int] = frozenset({0, 1, 131567, 9606})
