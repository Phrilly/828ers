DROP PROCEDURE IF EXISTS `sp_refresh_best_8_flags`;
-- END_QUERY

-- WATERMARK 1.0.41
CREATE PROCEDURE `sp_refresh_best_8_flags`(IN p_player_id INT)
BEGIN
    -- 1. Clear all existing flags for this player
    UPDATE wp_golf_handicap_history
    SET is_best_8 = 0
    WHERE player_id = p_player_id;

    -- 2. Identify and set is_best_8 = 1 for the best 8 of the last 20 rounds
    UPDATE wp_golf_handicap_history h
    INNER JOIN (
        SELECT score_id
        FROM (
            -- Added date_played to the select list so the outer query can use it
            SELECT score_id, differential, date_played
            FROM wp_golf_handicap_history
            WHERE player_id = p_player_id
            ORDER BY date_played DESC, score_id DESC
            LIMIT 20
        ) AS last_20
        -- THE FIX: Tie-breaker added here (Date descending, then ID descending)
        ORDER BY differential ASC, date_played DESC, score_id DESC
        LIMIT 8
    ) AS best_8 ON h.score_id = best_8.score_id
    SET h.is_best_8 = 1;
END;
-- END_QUERY