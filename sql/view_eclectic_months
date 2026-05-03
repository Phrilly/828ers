CREATE OR REPLACE VIEW view_eclectic_months AS
SELECT DISTINCT
    MONTH(s.date_played) AS month_num,
    YEAR(s.date_played)  AS year_num
FROM wp_golf_scores s
JOIN wp_golf_tees t    ON s.tee_id    = t.tee_id
JOIN wp_golf_courses c ON t.course_id = c.course_id
WHERE s.is_excluded = 0
  AND c.course_name = 'Ramsey Golf Club'
ORDER BY year_num DESC, month_num DESC;