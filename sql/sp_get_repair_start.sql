DROP PROCEDURE IF EXISTS `sp_get_repair_start`;
-- END_QUERY

CREATE PROCEDURE `sp_get_repair_start`(IN p_player_id INT, IN p_reference_date DATE, OUT p_start_date DATE)
BEGIN
    -- WATERMARK 1.1.31
    DECLARE v_window_start DATE;
    DECLARE v_scan_end DATE;
    DECLARE v_earliest_esr_date DATE;
    DECLARE v_expanded_start DATE;
    DECLARE v_done TINYINT DEFAULT 0;

    -- Start with the usual 20-round repair window.
    SELECT MIN(date_played) INTO v_window_start
    FROM (
        SELECT date_played
        FROM wp_golf_scores
        WHERE player_id = p_player_id
          AND date_played < p_reference_date
        ORDER BY date_played DESC, score_id DESC
        LIMIT 20
    ) AS prior_20;

    SET v_scan_end = p_reference_date;

    -- Each pass checks only the newly added part of the repair window.
    REPEAT
        SELECT MIN(s.date_played) INTO v_earliest_esr_date
        FROM wp_golf_scores s
        JOIN wp_golf_handicap_history h ON h.score_id = s.score_id
        WHERE s.player_id = p_player_id
          AND s.date_played >= COALESCE(v_window_start, p_reference_date)
          AND s.date_played < v_scan_end
          AND h.esr_triggered = 1;

        IF v_earliest_esr_date IS NOT NULL THEN
            SELECT MIN(date_played) INTO v_expanded_start
            FROM (
                SELECT s2.date_played
                FROM wp_golf_scores s2
                WHERE s2.player_id = p_player_id
                  AND s2.date_played < v_earliest_esr_date
                ORDER BY s2.date_played DESC, s2.score_id DESC
                LIMIT 20
            ) AS earlier_20;

            IF v_expanded_start IS NULL THEN
                SET v_done = 1;
            ELSE
                SET v_scan_end = v_window_start;
                SET v_window_start = v_expanded_start;
            END IF;
        ELSE
            SET v_done = 1;
        END IF;
    UNTIL v_done = 1 END REPEAT;

    SET p_start_date = COALESCE(v_window_start, p_reference_date);
END;
-- END_QUERY
