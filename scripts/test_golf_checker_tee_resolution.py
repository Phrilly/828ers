import os
import sys
import types
import unittest
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from unittest.mock import patch


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)


def install_dependency_stubs() -> None:
    config = types.ModuleType("config")
    config.DB_PREFIX = "wp_"
    sys.modules.setdefault("config", config)

    requests = types.ModuleType("requests")
    requests.Session = object
    requests.utils = types.SimpleNamespace()
    sys.modules.setdefault("requests", requests)

    bs4 = types.ModuleType("bs4")
    bs4.BeautifulSoup = object
    sys.modules.setdefault("bs4", bs4)

    pymysql = types.ModuleType("pymysql")
    pymysql.cursors = types.SimpleNamespace(DictCursor=object)
    sys.modules.setdefault("pymysql", pymysql)


install_dependency_stubs()

from eg_utils import EGRatingError, EGRoundRatings, parse_eg_round_ratings
from golf_checker import (
    FeedDataError,
    build_target_date_set,
    ensure_course_and_tee,
    insert_score,
    load_recent_manual_dates,
    normalize_course_name,
    process_eg_round,
    resolve_tee,
)


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.lastrowid = connection.next_id

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[Any],
    ) -> None:
        return None

    def execute(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> None:
        normalized_params = tuple(params) if params is not None else tuple()
        self.connection.statements.append((sql, normalized_params))
        if sql.lstrip().upper().startswith("INSERT"):
            self.lastrowid = self.connection.next_id

    def fetchall(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in self.connection.existing_rows]

    def fetchone(self) -> Optional[Dict[str, Any]]:
        if not self.connection.fetchone_rows:
            return None
        return dict(self.connection.fetchone_rows.pop(0))


class FakeConnection:
    def __init__(
        self,
        existing_rows: Optional[Sequence[Mapping[str, Any]]] = None,
        fetchone_rows: Optional[Sequence[Mapping[str, Any]]] = None,
        next_id: int = 99,
    ) -> None:
        self.existing_rows = list(existing_rows or [])
        self.fetchone_rows = list(fetchone_rows or [])
        self.next_id = next_id
        self.statements: List[Tuple[str, Tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_raw(**overrides: Any) -> Dict[str, Any]:
    raw: Dict[str, Any] = {
        "FacilityId": 101,
        "FacilityName": "Course A",
        "Marker": "White",
        "CourseRating": "71.4",
        "Slope": "128",
        "Par": "72",
    }
    raw.update(overrides)
    return raw


def make_scorecard(total_par: int = 72) -> Dict[str, Any]:
    scorecard: Dict[str, Any] = {"TotalPar": total_par}
    for hole_number in range(1, 19):
        scorecard[f"Hole{hole_number}Par"] = 4
    return scorecard


class EnglandGolfRatingTests(unittest.TestCase):
    def test_build_target_date_set_includes_full_range(
        self: "EnglandGolfRatingTests",
    ) -> None:
        dates = build_target_date_set("2026-08-07", "2026-08-16")

        self.assertEqual(
            dates,
            {
                "2026-08-07",
                "2026-08-08",
                "2026-08-09",
                "2026-08-10",
                "2026-08-11",
                "2026-08-12",
                "2026-08-13",
                "2026-08-14",
                "2026-08-15",
                "2026-08-16",
            },
        )

    def test_reads_and_checks_all_round_ratings(
        self: "EnglandGolfRatingTests",
    ) -> None:
        ratings = parse_eg_round_ratings(make_raw(), make_scorecard())

        self.assertEqual(ratings.course_rating, 71.4)
        self.assertEqual(ratings.slope_rating, 128)
        self.assertEqual(ratings.par, 72)
        self.assertEqual(ratings.par_source, "Par")

    def test_uses_course_par_then_scorecard_total_par(
        self: "EnglandGolfRatingTests",
    ) -> None:
        course_par = parse_eg_round_ratings(
            make_raw(Par=None, CoursePar="72"),
            make_scorecard(),
        )
        scorecard_par = parse_eg_round_ratings(
            make_raw(Par=None, CoursePar=None),
            make_scorecard(),
        )

        self.assertEqual(course_par.par_source, "CoursePar")
        self.assertEqual(scorecard_par.par_source, "TotalPar")

    def test_rejects_missing_or_inconsistent_ratings(
        self: "EnglandGolfRatingTests",
    ) -> None:
        with self.assertRaises(EGRatingError):
            parse_eg_round_ratings(make_raw(CourseRating=None), make_scorecard())

        with self.assertRaises(EGRatingError):
            parse_eg_round_ratings(make_raw(Par="71"), make_scorecard())


class TeeResolutionTests(unittest.TestCase):
    def test_normalizes_common_course_name_suffixes(
        self: "TeeResolutionTests",
    ) -> None:
        self.assertEqual(
            normalize_course_name("Ramsey"),
            normalize_course_name("Ramsey Golf Club"),
        )
        self.assertEqual(
            normalize_course_name("Example Golf Course"),
            "example",
        )

    def test_matches_ramsey_to_ramsey_golf_club(
        self: "TeeResolutionTests",
    ) -> None:
        tees = [
            {
                "tee_id": 7,
                "tee_colour": "White",
                "course_id": 1,
                "course_name": "Ramsey Golf Club",
                "eg_club_id": 101345,
            }
        ]

        result = resolve_tee(
            make_raw(FacilityId=None, FacilityName="Ramsey"),
            tees,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["course_id"], 1)

    def test_matches_course_and_colour_not_first_colour(
        self: "TeeResolutionTests",
    ) -> None:
        tees = [
            {
                "tee_id": 1,
                "tee_colour": "White",
                "course_id": 20,
                "course_name": "Course B",
                "eg_club_id": 202,
            },
            {
                "tee_id": 7,
                "tee_colour": "White",
                "course_id": 10,
                "course_name": "Course A",
                "eg_club_id": 101,
            },
        ]

        result = resolve_tee(make_raw(), tees)

        self.assertIsNotNone(result)
        self.assertEqual(result["tee_id"], 7)

    def test_updates_existing_tee_from_eg_values(
        self: "TeeResolutionTests",
    ) -> None:
        connection = FakeConnection()
        tees = [
            {
                "tee_id": 7,
                "tee_colour": "White",
                "course_id": 10,
                "course_name": "Course A",
                "eg_club_id": 101,
                "course_rating": "70.1",
                "slope_rating": 120,
                "par": 71,
            }
        ]
        ratings = EGRoundRatings(71.4, 128, 72, "Par")

        result = ensure_course_and_tee(
            connection,
            make_raw(),
            tees,
            ratings,
        )

        update_statements = [
            statement
            for statement in connection.statements
            if statement[0].lstrip().upper().startswith("UPDATE")
        ]
        self.assertEqual(len(update_statements), 1)
        self.assertEqual(update_statements[0][1], (71.4, 128, 72, 7))
        self.assertEqual(result["course_rating"], 71.4)
        self.assertTrue(result["ratings_changed"])

    def test_preview_reports_tee_change_without_writing(
        self: "TeeResolutionTests",
    ) -> None:
        connection = FakeConnection()
        tees = [
            {
                "tee_id": 7,
                "tee_colour": "White",
                "course_id": 10,
                "course_name": "Course A",
                "eg_club_id": 101,
                "course_rating": "70.1",
                "slope_rating": 120,
                "par": 71,
            }
        ]
        ratings = EGRoundRatings(71.4, 128, 72, "Par")

        result = ensure_course_and_tee(
            connection,
            make_raw(),
            tees,
            ratings,
            preview=True,
        )

        self.assertEqual(connection.statements, [])
        self.assertTrue(result["ratings_changed"])


class ScoreWriteTests(unittest.TestCase):
    def setUp(self: "ScoreWriteTests") -> None:
        self.ratings = EGRoundRatings(71.4, 128, 72, "Par")
        self.tee = {
            "tee_id": 7,
            "course_id": 10,
            "tee_colour": "White",
        }

    def test_overwrites_eg_fields_without_touching_manual_fields(
        self: "ScoreWriteTests",
    ) -> None:
        connection = FakeConnection(
            existing_rows=[
                {
                    "score_id": 44,
                    "tee_id": 7,
                    "gross_score": 90,
                    "pcc_adjustment": 0,
                    "course_id": 10,
                    "tee_colour": "White",
                }
            ]
        )

        score_id, inserted = insert_score(
            connection,
            player_id=3,
            date_played="2026-08-08",
            tee_row=self.tee,
            gross_score=88,
            pcc=1,
            ratings=self.ratings,
        )

        update_sql, update_params = connection.statements[-1]
        self.assertEqual(score_id, 44)
        self.assertFalse(inserted)
        self.assertNotIn("putts", update_sql)
        self.assertNotIn("gir", update_sql)
        self.assertNotIn("is_excluded", update_sql)
        self.assertEqual(update_params[:6], (7, 88, 1, 71.4, 128, 72))
        self.assertEqual(update_params[-1], 44)

    def test_inserts_complete_new_round(
        self: "ScoreWriteTests",
    ) -> None:
        connection = FakeConnection(next_id=55)

        score_id, inserted = insert_score(
            connection,
            player_id=3,
            date_played="2026-08-08",
            tee_row=self.tee,
            gross_score=88,
            pcc=1,
            ratings=self.ratings,
        )

        insert_sql, insert_params = connection.statements[-1]
        self.assertEqual(score_id, 55)
        self.assertTrue(inserted)
        self.assertIn("round_course_rating", insert_sql)
        self.assertIn("round_slope_rating", insert_sql)
        self.assertIn("round_par", insert_sql)
        self.assertEqual(insert_params[5:8], (71.4, 128, 72))
        self.assertEqual(insert_params[8], "eg_import")

    def test_rejects_course_or_tee_mismatch(
        self: "ScoreWriteTests",
    ) -> None:
        connection = FakeConnection(
            existing_rows=[
                {
                    "score_id": 44,
                    "tee_id": 9,
                    "gross_score": 90,
                    "pcc_adjustment": 0,
                    "course_id": 20,
                    "tee_colour": "White",
                }
            ]
        )

        with self.assertRaises(FeedDataError):
            insert_score(
                connection,
                player_id=3,
                date_played="2026-08-08",
                tee_row=self.tee,
                gross_score=88,
                pcc=1,
                ratings=self.ratings,
            )

        self.assertEqual(len(connection.statements), 1)

    def test_preview_performs_no_update_or_insert(
        self: "ScoreWriteTests",
    ) -> None:
        connection = FakeConnection()

        score_id, inserted = insert_score(
            connection,
            player_id=3,
            date_played="2026-08-08",
            tee_row=self.tee,
            gross_score=88,
            pcc=1,
            ratings=self.ratings,
            preview=True,
        )

        self.assertIsNone(score_id)
        self.assertTrue(inserted)
        self.assertEqual(len(connection.statements), 1)

    def test_process_rolls_back_tee_change_when_score_write_fails(
        self: "ScoreWriteTests",
    ) -> None:
        connection = FakeConnection()
        tees: List[Mapping[str, Any]] = [
            {
                "tee_id": 7,
                "tee_colour": "White",
                "course_id": 10,
                "course_name": "Course A",
                "eg_club_id": 101,
                "course_rating": "70.1",
                "slope_rating": 120,
                "par": 71,
            }
        ]

        with patch(
            "golf_checker.insert_score",
            side_effect=RuntimeError("forced score failure"),
        ):
            with self.assertRaises(RuntimeError):
                process_eg_round(
                    connection,
                    raw=make_raw(),
                    scorecard=make_scorecard(),
                    tees_list=tees,
                    player_id=3,
                    date_played="2026-08-08",
                    gross_score=88,
                    pcc=1,
                )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(
            any(
                sql.lstrip().upper().startswith("UPDATE")
                and "golf_tees" in sql
                for sql, _params in connection.statements
            )
        )

    def test_process_preview_rolls_back_read_transaction(
        self: "ScoreWriteTests",
    ) -> None:
        connection = FakeConnection()
        tees: List[Mapping[str, Any]] = [
            {
                "tee_id": 7,
                "tee_colour": "White",
                "course_id": 10,
                "course_name": "Course A",
                "eg_club_id": 101,
                "course_rating": "71.4",
                "slope_rating": 128,
                "par": 72,
            }
        ]

        with patch(
            "golf_checker.insert_score",
            return_value=(44, False),
        ):
            process_eg_round(
                connection,
                raw=make_raw(),
                scorecard=make_scorecard(),
                tees_list=tees,
                player_id=3,
                date_played="2026-08-08",
                gross_score=88,
                pcc=1,
                preview=True,
            )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)


class DelayedRecordTests(unittest.TestCase):
    def test_loads_recent_manual_rounds_for_rechecking(
        self: "DelayedRecordTests",
    ) -> None:
        connection = FakeConnection(
            existing_rows=[
                {"date_played": "2026-08-06"},
                {"date_played": "2026-08-08"},
            ]
        )

        dates = load_recent_manual_dates(
            connection,
            player_id=3,
            check_date="2026-08-08",
        )

        sql, params = connection.statements[0]
        self.assertIn("rating_source='manual_placeholder'", sql)
        self.assertIn("INTERVAL 7 DAY", sql)
        self.assertEqual(params, (3, "2026-08-08", "2026-08-08"))
        self.assertEqual(dates, ["2026-08-06", "2026-08-08"])


if __name__ == "__main__":
    unittest.main()
