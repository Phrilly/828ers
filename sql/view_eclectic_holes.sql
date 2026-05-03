CREATE OR REPLACE VIEW view_eclectic_holes AS
SELECT DISTINCT
    h.hole_number,
    h.par
FROM wp_golf_holes h
JOIN wp_golf_tees t    ON h.tee_id    = t.tee_id
JOIN wp_golf_courses c ON t.course_id = c.course_id
WHERE c.course_name = 'Ramsey Golf Club'
ORDER BY h.hole_number ASC;