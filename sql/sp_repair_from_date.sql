DROP PROCEDURE IF EXISTS `sp_repair_from_date`;
-- END_QUERY

CREATE PROCEDURE `sp_repair_from_date`(IN p_player_id INT, IN p_start_date DATE)
BEGIN
-- WATERMARK 1.0.27 --
    DECLARE v_score_id INT;
    DECLARE v_done TINYINT DEFAULT 0;

    DECLARE cur CURSOR FOR
        SELECT score_id FROM wp_golf_scores
        WHERE  player_id   = p_player_id
        AND    date_played >= p_start_date
        AND    is_excluded  = 0
        ORDER BY date_played ASC, score_id ASC;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    -- Reset history for the range to avoid compounding errors
    UPDATE wp_golf_handicap_history
    SET    esr_adj = 0.0, differential = diff_raw, esr_triggered = 0, esr_amount = 0.0
    WHERE  player_id   = p_player_id
    AND    date_played >= p_start_date;

    -- Clean up orphaned or excluded records
    DELETE h FROM wp_golf_handicap_history h
    LEFT JOIN wp_golf_scores s ON s.score_id = h.score_id
    WHERE h.player_id   = p_player_id
    AND   h.date_played >= p_start_date
    AND   (s.score_id IS NULL OR s.is_excluded = 1);

    OPEN cur;
    readloop: LOOP
        FETCH cur INTO v_score_id;
        IF v_done THEN LEAVE readloop; END IF;
        CALL sp_process_single_round(v_score_id, 0);
    END LOOP;
    CLOSE cur;

    -- Note: Ensure the name matches your other file (best_8 vs best8)
    CALL sp_refresh_best_8_flags(p_player_id);
END;
-- END_QUERY