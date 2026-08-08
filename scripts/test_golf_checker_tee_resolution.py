import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from golf_checker import resolve_tee


def test_resolve_tee_by_marker_when_rating_data_missing():
    raw = {"Marker": "White"}
    tees_list = [
        {"tee_id": 7, "tee_colour": "White", "course_rating": "72.0", "slope_rating": "125"},
    ]

    result = resolve_tee(raw, tees_list)
    assert result is not None
    assert result["tee_id"] == 7
    assert result["tee_colour"].lower() == "white"


if __name__ == "__main__":
    test_resolve_tee_by_marker_when_rating_data_missing()
    print("tee resolution regression test passed")
