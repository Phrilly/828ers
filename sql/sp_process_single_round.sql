DROP PROCEDURE IF EXISTS `sp_process_single_round`;
-- END_QUERY

CREATE PROCEDURE `sp_process_single_round`(IN p_score_id INT)
sp_label: BEGIN
-- WATERMARK 1.0.75 --
    DECLARE v_player_id     INT;
    DECLARE v_date_played   DATE;
    DECLARE v_gross_score   INT;
    DECLARE v_pcc           DECIMAL(4,1);
    DECLARE v_course_rating DECIMAL(4,1);
    DECLARE v_slope_rating  INT;
    DECLARE v_par           INT;
    -- Intermediate Variables (High Precision)
    DECLARE v_diff_raw      DECIMAL(5,1); 
    DECLARE v_hcp_before    DECIMAL(5,1);
    DECLARE v_hcp_unadj     DECIMAL(5,3); 
    DECLARE v_hcp_working   DECIMAL(5,3); 
    DECLARE v_low_hi_365    DECIMAL(5,3);
    DECLARE v_esr_amount    DECIMAL(5,2) DEFAULT 0.00;
    DECLARE v_cap_type      VARCHAR(10)  DEFAULT 'NONE';
    DECLARE v_cap_reduction DECIMAL(5,3) DEFAULT 0.000;
    DECLARE v_cap_original  DECIMAL(5,3);
    DECLARE v_course_hcp    DECIMAL(5,2);
    DECLARE v_playing_hcp   INT;
    DECLARE v_net_score     INT;

        SELECT s.player_id, s.date_played, s.gross_score,
            COALESCE(s.pcc_adjustment, 0),
            COALESCE(s.round_course_rating, t.course_rating),
            COALESCE(s.round_slope_rating, t.slope_rating),
            COALESCE(s.round_par, t.par)
    INTO   v_player_id, v_date_played, v_gross_score, v_pcc,
           v_course_rating, v_slope_rating, v_par
    FROM   wp_golf_scores s
    JOIN   wp_golf_tees   t ON s.tee_id = t.tee_id
    WHERE  s.score_id = p_score_id;

    IF (SELECT is_excluded FROM wp_golf_scores WHERE score_id = p_score_id) = 1 THEN
        DELETE FROM wp_golf_handicap_history WHERE score_id = p_score_id;
        LEAVE sp_label;
    END IF;

    -- 1. Calculate Score Differential (Round to 1 DP immediately)
    SET v_diff_raw = ROUND(113.0 / v_slope_rating * (v_gross_score - v_course_rating - v_pcc), 1);

    INSERT INTO wp_golf_handicap_history
        (player_id, score_id, date_played, diff_raw, differential, esr_adj, esr_triggered, esr_amount, cap_type, cap_reduction)
    VALUES
        (v_player_id, p_score_id, v_date_played, v_diff_raw, v_diff_raw, 0.0, 0, 0.0, 'NONE', 0.000)
    ON DUPLICATE KEY UPDATE
        diff_raw = v_diff_raw, differential = v_diff_raw, cap_type = 'NONE', cap_reduction = 0.000;

    -- 2. Get Handicap Before
    SELECT COALESCE(
        (SELECT hcp_after FROM wp_golf_handicap_history
         WHERE player_id = v_player_id
         AND (date_played < v_date_played OR (date_played = v_date_played AND score_id < p_score_id))
         ORDER BY date_played DESC, score_id DESC LIMIT 1), 54.0
    ) INTO v_hcp_before;
    UPDATE wp_golf_handicap_history SET hcp_before = v_hcp_before WHERE score_id = p_score_id;

    -- 3. Calculate Raw Average (Best 8 of 20)
    SELECT ROUND(AVG(d), 3) INTO v_hcp_unadj
    FROM (
        SELECT differential AS d FROM (
            SELECT differential FROM wp_golf_handicap_history
            WHERE player_id = v_player_id
            AND (date_played < v_date_played OR (date_played = v_date_played AND score_id <= p_score_id))
            ORDER BY date_played DESC, score_id DESC LIMIT 20
        ) AS last20 ORDER BY differential ASC LIMIT 8
    ) AS best8;
    
    SET v_hcp_working = ROUND(v_hcp_unadj, 1);
    UPDATE wp_golf_handicap_history SET hcp_unadjusted = v_hcp_unadj WHERE score_id = p_score_id;

    -- 4. ESR Check
    IF v_diff_raw <= v_hcp_before - 7.0 THEN
        SET v_esr_amount = CASE WHEN v_diff_raw < v_hcp_before - 10.0 THEN -2.00 ELSE -1.00 END;
        
        UPDATE wp_golf_handicap_history h
        INNER JOIN (
            SELECT score_id FROM wp_golf_handicap_history WHERE player_id = v_player_id
            AND (date_played < v_date_played OR (date_played = v_date_played AND score_id <= p_score_id))
            ORDER BY date_played DESC, score_id DESC LIMIT 20
        ) AS l20 ON h.score_id = l20.score_id
        SET h.esr_adj = h.esr_adj + v_esr_amount, h.differential = h.diff_raw + h.esr_adj + v_esr_amount;

        UPDATE wp_golf_handicap_history
        SET esr_triggered = 1,
            esr_amount = v_esr_amount
        WHERE score_id = p_score_id;

        -- Recalculate working average after ESR
        SELECT ROUND(AVG(d), 3) INTO v_hcp_working
        FROM (
            SELECT differential AS d FROM (
                SELECT differential FROM wp_golf_handicap_history WHERE player_id = v_player_id
                AND (date_played < v_date_played OR (date_played = v_date_played AND score_id <= p_score_id))
                ORDER BY date_played DESC, score_id DESC LIMIT 20
            ) AS l20 ORDER BY differential ASC LIMIT 8
        ) AS b8;
    END IF;

    -- 5. Soft/Hard Cap Math (Use the rounded Handicap Index as the cap input)
    SELECT COALESCE(MIN(hcp_after), v_hcp_working) INTO v_low_hi_365
    FROM wp_golf_handicap_history WHERE player_id = v_player_id
    AND date_played >= DATE_SUB(v_date_played, INTERVAL 1 YEAR)
    AND (date_played < v_date_played OR (date_played = v_date_played AND score_id < p_score_id));

    SET v_cap_original = v_hcp_working;
    IF v_hcp_working > v_low_hi_365 + 3.0 THEN
        SET v_cap_type = 'SOFT';
        SET v_hcp_working = v_low_hi_365 + 3.0 + (v_hcp_working - (v_low_hi_365 + 3.0)) * 0.5;
        IF v_hcp_working > v_low_hi_365 + 5.0 THEN
            SET v_cap_type = 'HARD';
            SET v_hcp_working = v_low_hi_365 + 5.0;
        END IF;
        SET v_cap_reduction = v_cap_original - v_hcp_working;
    END IF;

    -- 6. Final Rounding to 1 DP
    UPDATE wp_golf_handicap_history
    SET hcp_after = ROUND(v_hcp_working, 1), 
        cap_type = v_cap_type, 
        cap_reduction = v_cap_reduction,
        low_hi_365 = v_low_hi_365
    WHERE score_id = p_score_id;

    -- 7. Course/Playing Handicap (Pre-Round Index!)
    SET v_course_hcp  = ROUND(v_hcp_before * v_slope_rating / 113.0 + (v_course_rating - v_par), 2);
    SET v_playing_hcp = ROUND(v_course_hcp * 0.95, 0);
    SET v_net_score   = v_gross_score - v_playing_hcp;
    
    UPDATE wp_golf_handicap_history
    SET course_hcp = v_course_hcp, playing_hcp = v_playing_hcp, net_score = v_net_score
    WHERE score_id = p_score_id;

    -- 8. Update the best 8 flags ---
    CALL sp_refresh_best_8_flags(v_player_id);

END;
-- END_QUERY