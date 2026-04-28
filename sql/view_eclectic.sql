CREATE OR REPLACE VIEW view_eclectic AS
SELECT
    p.player_id,
    hbh.player_name,
    hbh.hole_number,
    hbh.par,
    MONTH(hbh.date_played)    AS month_num,
    YEAR(hbh.date_played)     AS year_num,
    MIN(hbh.gross_score)      AS best_gross,
    MAX(hbh.stableford_score) AS best_stableford
FROM view_golf_hole_by_hole hbh
JOIN wp_golf_scores s  ON hbh.score_id  = s.score_id
JOIN wp_golf_players p ON s.player_id   = p.player_id
WHERE hbh.course_name = 'Ramsey Golf Club'
  AND (
      SELECT COUNT(DISTINCT s2.player_id)
      FROM wp_golf_scores s2
      WHERE s2.date_played = hbh.date_played
        AND s2.tee_id      = s.tee_id
        AND s2.is_excluded = 0
  ) > 1
GROUP BY
    p.player_id,
    hbh.player_name,
    hbh.hole_number,
    hbh.par,
    MONTH(hbh.date_played),
    YEAR(hbh.date_played);