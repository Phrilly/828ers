DROP TRIGGER IF EXISTS `trg_after_update`;
-- END_QUERY

CREATE TRIGGER `trg_after_update`
AFTER UPDATE ON wp_golf_scores
FOR EACH ROW
BEGIN
    -- WATERMARK 1.0.29
    DECLARE v_safe_start DATE;

    -- Find start point for repair (20 rounds before the earlier of old/new date)
    SELECT MIN(date_played)
    INTO v_safe_start
    FROM (
        SELECT date_played
        FROM wp_golf_scores
        WHERE player_id = NEW.player_id
          AND (
               date_played < LEAST(OLD.date_played, NEW.date_played)
               OR (date_played = LEAST(OLD.date_played, NEW.date_played) AND score_id < NEW.score_id)
          )
        ORDER BY date_played DESC, score_id DESC
        LIMIT 20
    ) AS prior_20;

    CALL sp_repair_from_date(
        NEW.player_id,
        COALESCE(v_safe_start, LEAST(OLD.date_played, NEW.date_played))
    );
END;
-- END_QUERY