DROP TRIGGER IF EXISTS `trg_after_update`;
-- END_QUERY

CREATE TRIGGER `trg_after_update`
AFTER UPDATE ON wp_golf_scores
FOR EACH ROW
BEGIN
    -- WATERMARK 1.0.30
    DECLARE v_safe_start DATE;
    DECLARE v_reference_date DATE;

    SET v_reference_date = LEAST(OLD.date_played, NEW.date_played);
    CALL sp_get_repair_start(NEW.player_id, v_reference_date, v_safe_start);

    CALL sp_repair_from_date(
        NEW.player_id,
        COALESCE(v_safe_start, v_reference_date)
    );
END;
-- END_QUERY