DROP TRIGGER IF EXISTS `trg_after_insert`;
-- END_QUERY

CREATE TRIGGER `trg_after_insert`
AFTER INSERT ON wp_golf_scores
FOR EACH ROW
BEGIN
    -- WATERMARK 1.0.30
    DECLARE v_is_backdated TINYINT DEFAULT 0;
    DECLARE v_safe_start   DATE;

    -- Check if there are any rounds that exist AFTER this new one
    SELECT EXISTS (
        SELECT 1 
        FROM wp_golf_scores 
        WHERE player_id = NEW.player_id 
          AND score_id != NEW.score_id 
          AND (date_played > NEW.date_played 
               OR (date_played = NEW.date_played AND score_id > NEW.score_id))
    ) INTO v_is_backdated;

    IF v_is_backdated THEN
        CALL sp_get_repair_start(NEW.player_id, NEW.date_played, v_safe_start);
        CALL sp_repair_from_date(NEW.player_id, COALESCE(v_safe_start, NEW.date_played));
    ELSE
        -- Just process the single new round
        CALL sp_process_single_round(NEW.score_id);
    END IF;
END;
-- END_QUERY