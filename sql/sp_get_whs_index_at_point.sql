DROP PROCEDURE IF EXISTS `sp_get_whs_index_at_point`;
-- END_QUERY

CREATE PROCEDURE `sp_get_whs_index_at_point`(
    IN p_player_id INT, 
    IN p_date DATE, 
    IN p_score_id INT, 
    OUT p_calculated_index DECIMAL(5,1)
)
BEGIN
    -- WATERMARK 1.0.22
    -- We use a triple-nested query to ensure the LIMIT 8 applies 
    -- to the sorted list of differentials, not the average.
    SELECT ROUND(AVG(best_8.diff), 1) INTO p_calculated_index
    FROM (
        SELECT last_20.diff
        FROM (
            -- 1. Get the last 20 scores BEFORE the current round
            SELECT differential AS diff
            FROM wp_golf_handicap_history
            WHERE player_id = p_player_id
              AND (date_played < p_date OR (date_played = p_date AND score_id < p_score_id))
            ORDER BY date_played DESC, score_id DESC
            LIMIT 20
        ) AS last_20
        -- 2. Sort those 20 from best (lowest) to worst
        ORDER BY last_20.diff ASC
        -- 3. Take only the best 8
        LIMIT 8
    ) AS best_8;

    -- Default for new players
    IF p_calculated_index IS NULL THEN SET p_calculated_index = 54.0; END IF;
END;
-- END_QUERY