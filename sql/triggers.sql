-- --------------------------------------------------------
-- 828ers GOLF SYSTEM: TRIGGERS
-- --------------------------------------------------------

DROP TRIGGER IF EXISTS `tg_after_score_insert`;
-- END_QUERY

CREATE TRIGGER `tg_after_score_insert` 
AFTER INSERT ON `wp_golf_scores`
FOR EACH ROW
BEGIN
    -- Automatically calculate handicap for the new round
    CALL sp_process_single_round(NEW.score_id);
END;
-- END_QUERY

DROP TRIGGER IF EXISTS `tg_after_score_update`;
-- END_QUERY

CREATE TRIGGER `tg_after_score_update` 
AFTER UPDATE ON `wp_golf_scores`
FOR EACH ROW
BEGIN
    -- Re-run calculation if the score or tee changed
    IF (OLD.gross_score <> NEW.gross_score OR OLD.tee_id <> NEW.tee_id OR OLD.is_excluded <> NEW.is_excluded) THEN
        CALL sp_process_single_round(NEW.score_id);
    END IF;
END;
-- END_QUERY