DROP TRIGGER IF EXISTS `trg_after_update`;
-- END_QUERY

CREATE TRIGGER `trg_after_update`
AFTER UPDATE ON wp_golf_scores
FOR EACH ROW
BEGIN
    -- WATERMARK 1.1.32
    DECLARE v_safe_start DATE;
    DECLARE v_reference_date DATE;
    DECLARE v_changed TINYINT DEFAULT 0;

    SET v_reference_date = LEAST(OLD.date_played, NEW.date_played);
    SET v_changed = (
        OLD.gross_score <> NEW.gross_score
        OR COALESCE(OLD.pcc_adjustment, 0) <> COALESCE(NEW.pcc_adjustment, 0)
        OR COALESCE(OLD.round_course_rating, 0) <> COALESCE(NEW.round_course_rating, 0)
        OR COALESCE(OLD.round_slope_rating, 0) <> COALESCE(NEW.round_slope_rating, 0)
        OR COALESCE(OLD.round_par, 0) <> COALESCE(NEW.round_par, 0)
        OR OLD.tee_id <> NEW.tee_id
    );

    IF v_changed = 1 THEN
        CALL sp_get_repair_start(NEW.player_id, v_reference_date, v_safe_start);
        CALL sp_repair_from_date(
            NEW.player_id,
            COALESCE(v_safe_start, v_reference_date)
        );
    END IF;
END;
-- END_QUERY