DROP PROCEDURE IF EXISTS `sp_rebuild_all_players`;
-- END_QUERY

CREATE PROCEDURE `sp_rebuild_all_players`()
BEGIN
    -- WATERMARK 1.0.25
    DECLARE v_player_id  INT;
    DECLARE v_first_date DATE;
    DECLARE v_done       TINYINT DEFAULT 0;

    DECLARE cur CURSOR FOR
        SELECT player_id, MIN(date_played)
        FROM   wp_golf_scores
        WHERE  is_excluded = 0
        GROUP BY player_id;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    TRUNCATE TABLE wp_golf_handicap_history;

    OPEN cur;
    playerloop: LOOP
        FETCH cur INTO v_player_id, v_first_date;
        IF v_done THEN LEAVE playerloop; END IF;
        CALL sp_repair_from_date(v_player_id, v_first_date);
    END LOOP;
    CLOSE cur;

    CALL sp_build_view_golf_rounds_pivot();
END;
-- END_QUERY