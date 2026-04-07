# tests/unit/test_reviewer_title.py

import pytest
from app.routers.users import reviewer_title


@pytest.mark.parametrize(
    "count, expected",
    [
        (0, "Newbie"),
        (1, "Initiate"),
        (4, "Initiate"),  # just below Novice threshold
        (5, "Novice"),
        (14, "Novice"),  # just below Apprentice threshold
        (15, "Apprentice"),
        (29, "Apprentice"),  # just below Disciple threshold
        (30, "Disciple"),
        (59, "Disciple"),  # just below Adept threshold
        (60, "Adept"),
        (99, "Adept"),  # just below Journeyman threshold
        (100, "Journeyman"),
        (174, "Journeyman"),  # just below Veteran threshold
        (175, "Veteran"),
        (249, "Veteran"),  # just below Expert threshold
        (250, "Expert"),
        (299, "Expert"),  # just below Master threshold
        (300, "Master"),
        (499, "Master"),  # just below Grand Master threshold
        (500, "Grand Master"),
        (999, "Grand Master"),  # well above max threshold
    ],
)
def test_reviewer_title(count, expected):
    assert reviewer_title(count) == expected
