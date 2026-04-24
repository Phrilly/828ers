CREATE OR REPLACE VIEW view_eclectic AS
SELECT
    p.player_id,
    p.name AS player_name,
    h.hole_number,
    h.par,
    MONTH(s.date_played)  AS month_num,
    YEAR(s.date_played)   AS year_num,
    MIN(hs.gross_score)   AS best_gross,
    MAX(
        GREATEST(0, 2 + h.par - (
            hs.gross_score - (
                FLOOR(COALESCE(hh.playing_hcp, 0) / 18) +
                CASE WHEN COALESCE(hh.playing_hcp, 0) MOD 18 >= h.stroke_index THEN 1 ELSE 0 END
            )
        ))
    ) AS best_stableford
FROM wp_golf_hole_scores hs
JOIN wp_golf_scores            s   ON hs.score_id  = s.score_id
JOIN wp_golf_players           p   ON s.player_id  = p.player_id
JOIN wp_golf_holes             h   ON hs.hole_id   = h.hole_id
JOIN wp_golf_tees              t   ON h.tee_id     = t.tee_id
JOIN wp_golf_courses           c   ON t.course_id  = c.course_id
LEFT JOIN wp_golf_handicap_history hh ON s.score_id = hh.score_id
WHERE s.is_excluded = 0
  AND c.course_name = 'Ramsey Golf Club'
GROUP BY
    p.player_id,
    p.name,
    h.hole_number,
    h.par,
    MONTH(s.date_played),
    YEAR(s.date_played)