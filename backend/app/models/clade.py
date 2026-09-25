# app/models/clade.py
"""Response models for the clade view: every taxon under one anchor taxon that
has signal in a sample or in the negative controls it is compared against
(see ``app.sample_controls``).

Built by ``app.clade``; never stored.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

# "reads" for taxprofiler classifiers, "fraction" for TRANA/Emu relative
# abundance. Reads-per-million only exists for "reads".
CladeUnit = Literal["reads", "fraction"]

# "deleted": NCBI deleted the ID. "not_in_taxonomy": the ID (or the ID it was
# merged into) has no placeable record in the loaded taxonomy.
UnplacedReason = Literal["deleted", "not_in_taxonomy"]


class _StrictBase(BaseModel):
    # Built by our own code, not read from Mongo: an unexpected field is a bug.
    model_config = ConfigDict(extra="forbid")


class CladeColumn(_StrictBase):
    sample_id: str
    # The first column is the viewed sample, which can itself be a control;
    # every other column is a negative control.
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    # False when this sample produced no profile for the classifier. Its cells
    # are then absent, which is different from zero signal.
    has_profile: bool
    # Sum of every row of the classifier's profile, unclassified included: the
    # reads-per-million denominator. None for "fraction" units or no profile.
    classifier_total: Optional[float] = None


class CladeCell(_StrictBase):
    # Signal assigned exactly to this taxon (taxpasta counts are direct).
    direct: float
    # Direct signal of this taxon plus everything below it in the tree.
    clade: float
    direct_rpm: Optional[float] = None
    clade_rpm: Optional[float] = None


class CladeTaxon(_StrictBase):
    taxon_id: int
    name: str
    rank: Optional[str] = None


class CladeNode(CladeTaxon):
    # Keyed by CladeColumn.sample_id; columns without a profile have no entry.
    cells: dict[str, CladeCell]
    # True when no column has direct signal on this taxon: it is only in the
    # tree to connect taxa below it to the anchor.
    is_connector: bool
    # Retired IDs found in the profiles whose signal was added to this taxon.
    merged_from: list[int] = []
    children: list["CladeNode"] = []


class UnplacedTaxon(_StrictBase):
    # The deleted ID, or the current ID that has no placeable taxonomy record.
    taxon_id: int
    # From the profile, since the taxonomy has no usable record.
    name: Optional[str] = None
    reason: UnplacedReason
    # Retired IDs found in the profiles whose signal was added to this taxon.
    merged_from: list[int] = []
    # Direct signal only — without a lineage there is no clade to sum.
    cells: dict[str, CladeCell]


class CladeResponse(_StrictBase):
    classifier: str
    unit: CladeUnit
    # The taxon the user clicked, after resolving a merged ID.
    clicked: CladeTaxon
    # Root of the tree: the clicked taxon's genus, or the clicked taxon itself
    # when it has no genus ancestor (genus or above, or many viruses).
    anchor: CladeTaxon
    # The sample first, then its negative controls by sample_id.
    columns: list[CladeColumn]
    root: CladeNode
    # Every taxon in the analysis that could not be placed in the taxonomy,
    # not only this clade's: an unplaced taxon may belong here.
    unplaced: list[UnplacedTaxon]
