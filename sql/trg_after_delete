DROP TRIGGER IF EXISTS `trg_after_delete`;
-- END_QUERY

CREATE TRIGGER `trg_after_delete`
AFTER DELETE ON wp_golf_scores
FOR EACH ROW
BEGIN
    -- WATERMARK 1.0.29
    DECLARE v_safe_start DATE;

    -- 1. Remove the record from history first
    DELETE FROM wp_golf_handicap_history WHERE score_id = OLD.score_id;

    -- 2. Find the repair start point (20 rounds before the deleted one)
    SELECT MIN(date_played)
    INTO v_safe_start
    FROM (
        SELECT date_played
        FROM wp_golf_scores
        WHERE player_id = OLD.player_id
          AND (
               date_played < OLD.date_played
               OR (date_played = OLD.date_played AND score_id < OLD.score_id)
          )
        ORDER BY date_played DESC, score_id DESC
        LIMIT 20
    ) AS prior_20;

    -- 3. Trigger the repair chain
    CALL sp_repair_from_date(
        OLD.player_id,
        COALESCE(v_safe_start, OLD.date_played)
    );
END;
-- END_QUERY