ALTER TABLE `wp_golf_scores`
    ADD COLUMN IF NOT EXISTS `round_course_rating` DECIMAL(4,1) NULL AFTER `tee_id`;
-- END_QUERY

ALTER TABLE `wp_golf_scores`
    ADD COLUMN IF NOT EXISTS `round_slope_rating` INT NULL AFTER `round_course_rating`;
-- END_QUERY

ALTER TABLE `wp_golf_scores`
    ADD COLUMN IF NOT EXISTS `round_par` INT NULL AFTER `round_slope_rating`;
-- END_QUERY

ALTER TABLE `wp_golf_scores`
    ADD COLUMN IF NOT EXISTS `rating_source` VARCHAR(32) NULL AFTER `round_par`;
-- END_QUERY

ALTER TABLE `wp_golf_scores`
    ADD COLUMN IF NOT EXISTS `rating_updated_at` DATETIME NULL AFTER `rating_source`;
-- END_QUERY - 1
