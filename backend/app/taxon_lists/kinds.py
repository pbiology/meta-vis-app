# app/taxon_lists/kinds.py
"""The kinds of taxon list and what each one allows.

Adding a new kind of list is one enum member plus one ``KIND_SPECS`` entry;
the router, store and frontend API are shared by every kind.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class TaxonListKind(StrEnum):
    OUTBREAK_IGNORE = "outbreak_ignore"
    KNOWN_PATHOGENS = "known_pathogens"
    NTC_IGNORE = "ntc_ignore"
    NTC_CONTAMINANTS = "ntc_contaminants"
    # Taxa a user can choose to hide from the taxonomy table. Display only:
    # never read by analytics, reports or totals.
    DISPLAY_FILTER = "display_filter"


@dataclass(frozen=True)
class KindSpec:
    # Kind-specific entry fields beyond the common ones, mapped to the default
    # used when an entry is created without them. Any other extra is rejected.
    extra_fields: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    # Whether a change alters cached analytics (outbreak alerts, NTC trends and
    # contaminant alerts), and so must bump the shared cache version.
    affects_analytics: bool = False
    # Whether users create and delete lists of this kind. The other kinds have
    # exactly one seeded system list each, which the analytics reference by id.
    user_creatable: bool = False


KIND_SPECS: Mapping[TaxonListKind, KindSpec] = MappingProxyType(
    {
        TaxonListKind.OUTBREAK_IGNORE: KindSpec(affects_analytics=True),
        TaxonListKind.KNOWN_PATHOGENS: KindSpec(),
        TaxonListKind.NTC_IGNORE: KindSpec(affects_analytics=True),
        TaxonListKind.NTC_CONTAMINANTS: KindSpec(
            extra_fields=MappingProxyType({"min_reads": 3}),
            affects_analytics=True,
        ),
        TaxonListKind.DISPLAY_FILTER: KindSpec(user_creatable=True),
    }
)

# A taxon may not sit on two lists whose kinds are paired here. Ignoring a
# taxon in NTC tracking and alerting on it as a known contaminant contradict
# each other: the trends would hide what the alerts flag.
MUTUALLY_EXCLUSIVE_KINDS: frozenset[frozenset[TaxonListKind]] = frozenset(
    {frozenset({TaxonListKind.NTC_IGNORE, TaxonListKind.NTC_CONTAMINANTS})}
)


# ---------------------------------------------------------------------------
# System lists — seeded at startup, one per non-user-creatable kind,
# referenced by consumers.
# ---------------------------------------------------------------------------

OUTBREAK_IGNORELIST = "outbreak_ignorelist"
KNOWN_PATHOGENS = "known_pathogens"
NTC_IGNORELIST = "ntc_ignorelist"
NTC_KNOWN_CONTAMINANTS = "ntc_known_contaminants"


@dataclass(frozen=True)
class SystemList:
    list_id: str
    kind: TaxonListKind
    name: str
    description: str


SYSTEM_LISTS: tuple[SystemList, ...] = (
    SystemList(
        OUTBREAK_IGNORELIST,
        TaxonListKind.OUTBREAK_IGNORE,
        "Outbreak ignorelist",
        "Taxa excluded from outbreak detection.",
    ),
    SystemList(
        KNOWN_PATHOGENS,
        TaxonListKind.KNOWN_PATHOGENS,
        "Known pathogens",
        "Curated pathogens highlighted in cases, samples and reports.",
    ),
    SystemList(
        NTC_IGNORELIST,
        TaxonListKind.NTC_IGNORE,
        "NTC ignorelist",
        "Taxa excluded from NTC trend tracking.",
    ),
    SystemList(
        NTC_KNOWN_CONTAMINANTS,
        TaxonListKind.NTC_CONTAMINANTS,
        "NTC known contaminants",
        "Known contaminants alerted on when found in negative controls.",
    ),
)
