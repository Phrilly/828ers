DROP TRIGGER IF EXISTS `trg_after_update`;
-- END_QUERY

CREATE TRIGGER `trg_after_update`
AFTER UPDATE ON wp_golf_scores
FOR EACH ROW
BEGIN
    -- WATERMARK 1.1.29
    DECLARE v_safe_start DATE;
    DECLARE v_reference_date DATE;
    DECLARE v_diff_raw DECIMAL(5,1);
    DECLARE v_hcp_before DECIMAL(5,1);
    DECLARE v_changed TINYINT DEFAULT 0;
    DECLARE v_was_esr TINYINT DEFAULT 0;
    DECLARE v_needs_repair TINYINT DEFAULT 0;

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

        SET v_was_esr = COALESCE(
            (
                SELECT esr_triggered
                FROM wp_golf_handicap_history
                WHERE score_id = NEW.score_id
            ),
            0
        );

        IF v_was_esr = 1 OR v_diff_raw <= v_hcp_before - 7.0 THEN
            SET v_needs_repair = 1;
        END IF;

        IF v_needs_repair = 1 THEN
            CALL sp_get_repair_start(NEW.player_id, v_reference_date, v_safe_start);
            CALL sp_repair_from_date(
                NEW.player_id,
                COALESCE(v_safe_start, v_reference_date)
            );
        ELSE
            CALL sp_process_single_round(NEW.score_id, 1);
        END IF;
    END IF;
END;
-- END_QUERY