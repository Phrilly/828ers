ALTER TABLE `wp_golf_scores`
    ADD COLUMN `round_course_rating` DECIMAL(4,1) NULL AFTER `tee_id`,
    ADD COLUMN `round_slope_rating` INT NULL AFTER `round_course_rating`,
    ADD COLUMN `round_par` INT NULL AFTER `round_slope_rating`,
    ADD COLUMN `rating_source` VARCHAR(32) NULL AFTER `round_par`,
    ADD COLUMN `rating_updated_at` DATETIME NULL AFTER `rating_source`;
-- END_QUERY
