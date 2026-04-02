# tests/unit/test_reviewer_title.py

import pytest
from app.routers.users import reviewer_title


@pytest.mark.parametrize("count, expected", [
    (0,   "Spore"),
    (1,   "Mycelium"),
    (4,   "Mycelium"),    # just below Puffball threshold
    (5,   "Puffball"),
    (14,  "Puffball"),    # just below Penny Bun threshold
    (15,  "Penny Bun"),
    (29,  "Penny Bun"),   # just below Chanterelle threshold
    (30,  "Chanterelle"),
    (59,  "Chanterelle"), # just below Oyster threshold
    (60,  "Oyster"),
    (99,  "Oyster"),      # just below Shiitake threshold
    (100, "Shiitake"),
    (174, "Shiitake"),    # just below Lion's Mane threshold
    (175, "Lion's Mane"),
    (299, "Lion's Mane"), # just below Morel threshold
    (300, "Morel"),
    (499, "Morel"),       # just below Truffle threshold
    (500, "Truffle"),
    (999, "Truffle"),     # well above max threshold
])
def test_reviewer_title(count, expected):
    assert reviewer_title(count) == expected