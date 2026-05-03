DROP VIEW IF EXISTS `view_golf_hole_analysis`;
-- END_QUERY

CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_hole_analysis` AS
WITH BaseScores AS (
    SELECT
        s.player_id,
        t.course_id,
        h.hole_number,
        h.par,
        h.stroke_index,
        hs.gross_score,
        (
            FLOOR(COALESCE(hh.playing_hcp, 0) / 18) +
            CASE
                WHEN (COALESCE(hh.playing_hcp, 0) % 18) >= h.stroke_index THEN 1
                ELSE 0
            END
        ) AS shots_received
    FROM wp_golf_hole_scores hs
    JOIN wp_golf_scores s
        ON hs.score_id = s.score_id
    JOIN wp_golf_holes h
        ON hs.hole_number = h.hole_number
       AND h.tee_id = s.tee_id
    JOIN wp_golf_tees t
        ON s.tee_id = t.tee_id
    LEFT JOIN wp_golf_handicap_history hh
        ON s.score_id = hh.score_id
    WHERE s.is_excluded = 0
),
CalculatedScores AS (
    SELECT
        *,
        (gross_score - shots_received) AS nett_score,
        GREATEST(0, (2 + par) - (gross_score - shots_received)) AS stableford_points
    FROM BaseScores
),
RawStats AS (
    SELECT
        player_id,
        course_id,
        hole_number,
        MAX(par) AS par,
        MAX(stroke_index) AS stroke_index,
        COUNT(gross_score) AS times_played,
        ROUND(AVG(gross_score), 2) AS avg_gross,
        ROUND(AVG(gross_score - par), 2) AS avg_to_par,
        ROUND(AVG(stableford_points), 2) AS avg_pts,
        ROUND(COALESCE(STDDEV_SAMP(gross_score), 0), 2) AS std_dev,
        MIN(gross_score) AS best_score,
        MAX(gross_score) AS worst_score,
        SUM(CASE WHEN gross_score - par <= -2 THEN 1 ELSE 0 END) AS eagles,
        SUM(CASE WHEN gross_score - par = -1 THEN 1 ELSE 0 END) AS birdies,
        SUM(CASE WHEN gross_score - par = 0 THEN 1 ELSE 0 END) AS pars,
        SUM(CASE WHEN gross_score - par = 1 THEN 1 ELSE 0 END) AS bogeys,
        SUM(CASE WHEN gross_score - par >= 2 THEN 1 ELSE 0 END) AS doubles_plus
    FROM CalculatedScores
    GROUP BY player_id, course_id, hole_number

    UNION ALL

    SELECT
        0 AS player_id,
        course_id,
        hole_number,
        MAX(par) AS par,
        MAX(stroke_index) AS stroke_index,
        COUNT(gross_score) AS times_played,
        ROUND(AVG(gross_score), 2) AS avg_gross,
        ROUND(AVG(gross_score - par), 2) AS avg_to_par,
        ROUND(AVG(stableford_points), 2) AS avg_pts,
        ROUND(COALESCE(STDDEV_SAMP(gross_score), 0), 2) AS std_dev,
        MIN(gross_score) AS best_score,
        MAX(gross_score) AS worst_score,
        SUM(CASE WHEN gross_score - par <= -2 THEN 1 ELSE 0 END) AS eagles,
        SUM(CASE WHEN gross_score - par = -1 THEN 1 ELSE 0 END) AS birdies,
        SUM(CASE WHEN gross_score - par = 0 THEN 1 ELSE 0 END) AS pars,
        SUM(CASE WHEN gross_score - par = 1 THEN 1 ELSE 0 END) AS bogeys,
        SUM(CASE WHEN gross_score - par >= 2 THEN 1 ELSE 0 END) AS doubles_plus
    FROM CalculatedScores
    GROUP BY course_id, hole_number
)
SELECT
    player_id,
    course_id,
    hole_number,
    par,
    stroke_index AS official_si,
    times_played,
    avg_gross,
    avg_to_par,
    avg_pts,
    std_dev,
    best_score,
    worst_score,
    eagles,
    birdies,
    pars,
    bogeys,
    doubles_plus,
    RANK() OVER (
        PARTITION BY player_id, course_id
        ORDER BY avg_to_par DESC
    ) AS actual_difficulty_rank
FROM RawStats;

-- END_QUERY