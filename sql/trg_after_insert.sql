DROP TRIGGER IF EXISTS `trg_after_insert`;
-- END_QUERY

CREATE TRIGGER `trg_after_insert`
AFTER INSERT ON wp_golf_scores
FOR EACH ROW
BEGIN
    -- WATERMARK 1.1.28
    DECLARE v_is_backdated TINYINT DEFAULT 0;
    DECLARE v_safe_start DATE;
    DECLARE v_diff_raw DECIMAL(5,1);
    DECLARE v_hcp_before DECIMAL(5,1);
    DECLARE v_needs_repair TINYINT DEFAULT 0;

    -- Check if there are any rounds that exist AFTER this new one
    SELECT EXISTS (
        SELECT 1 
        FROM wp_golf_scores 
        WHERE player_id = NEW.player_id 
          AND score_id != NEW.score_id 
          AND (date_played > NEW.date_played 
               OR (date_played = NEW.date_played AND score_id > NEW.score_id))
    ) INTO v_is_backdated;

    SET v_diff_raw = ROUND(
        113.0 / NEW.round_slope_rating * (NEW.gross_score - NEW.round_course_rating - COALESCE(NEW.pcc_adjustment, 0)),
        1
    );

    SELECT COALESCE(
        (
            SELECT hcp_after
            FROM wp_golf_handicap_history
            WHERE player_id = NEW.player_id
              AND (
                date_played < NEW.date_played
                OR (date_played = NEW.date_played AND score_id < NEW.score_id)
              )
            ORDER BY date_played DESC, score_id DESC
            LIMIT 1
        ),
        54.0
    ) INTO v_hcp_before;

    IF v_diff_raw <= v_hcp_before - 7.0 THEN
        SET v_needs_repair = 1;
    END IF;

    IF v_is_backdated = 1 OR v_needs_repair = 1 THEN
        CALL sp_get_repair_start(NEW.player_id, NEW.date_played, v_safe_start);
        CALL sp_repair_from_date(NEW.player_id, COALESCE(v_safe_start, NEW.date_played));
    ELSE
        -- Just process the single new round.
        CALL sp_process_single_round(NEW.score_id, 1);
    END IF;
END;
-- END_QUERY