UPDATE `wp_golf_scores` s
JOIN `wp_golf_tees` t ON t.tee_id = s.tee_id
SET
    s.round_course_rating = COALESCE(s.round_course_rating, t.course_rating),
    s.round_slope_rating  = COALESCE(s.round_slope_rating, t.slope_rating),
    s.round_par           = COALESCE(s.round_par, t.par),
    s.rating_source       = COALESCE(s.rating_source, 'tee_backfill'),
    s.rating_updated_at   = COALESCE(s.rating_updated_at, NOW())
WHERE
    s.round_course_rating IS NULL
    OR s.round_slope_rating IS NULL
    OR s.round_par IS NULL
    OR s.rating_source IS NULL
    OR s.rating_updated_at IS NULL;
-- END_QUERY
