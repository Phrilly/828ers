CREATE OR REPLACE VIEW view_eclectic AS
SELECT
    p.player_id,
    p.name AS player_name,
    h.hole_number,
    h.par,
    MONTH(s.date_played)  AS month_num,
    YEAR(s.date_played)   AS year_num,
    MIN(hs.gross_score)   AS best_gross,
    MAX(hs.stableford_score) AS best_stableford   -- ✅ Use the saved value directly
FROM wp_golf_hole_scores hs
JOIN wp_golf_scores s
    ON hs.score_id = s.score_id
JOIN wp_golf_players p
    ON s.player_id = p.player_id
JOIN wp_golf_holes h
    ON hs.hole_id = h.hole_id
JOIN wp_golf_tees t
    ON h.tee_id = t.tee_id
JOIN wp_golf_courses c
    ON t.course_id = c.course_id
WHERE s.is_excluded = 0
  AND c.course_name = 'Ramsey Golf Club'
  AND (
      SELECT COUNT(DISTINCT s2.player_id)
      FROM wp_golf_scores s2
      WHERE s2.date_played = s.date_played
        AND s2.tee_id = s.tee_id
        AND s2.is_excluded = 0
  ) > 1
GROUP BY
    p.player_id,
    p.name,
    h.hole_number,
    h.par,
    MONTH(s.date_played),
    YEAR(s.date_played);