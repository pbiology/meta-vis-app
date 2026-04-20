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

# Contaminant flagging: a sample taxon is flagged as a potential contaminant
# when the sum of its reads across the case's NTCs (same material, same
# classifier) exceeds this threshold, AND the taxon's rank is in the
# eligible set. Ranks broader than genus are deliberately excluded — a hit
# at family level or above is too vague to act on.
CONTAMINANT_NTC_READ_THRESHOLD: int = 5
CONTAMINANT_ELIGIBLE_RANKS: frozenset[str] = frozenset(
    {"genus", "species", "subspecies", "strain", "serotype", "no rank"}
)
