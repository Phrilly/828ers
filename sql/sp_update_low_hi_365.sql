DROP PROCEDURE IF EXISTS `sp_update_low_hi_365`;
-- END_QUERY

CREATE PROCEDURE `sp_update_low_hi_365`(IN p_score_id INT)
BEGIN
  -- WATERMARK 1.1.33
  DECLARE v_player_id INT;
  DECLARE v_date_played DATE;
  DECLARE v_previous_score_date DATE;
  DECLARE v_low_hi DECIMAL(5,2);

  SELECT s.player_id, s.date_played
    INTO v_player_id, v_date_played
  FROM wp_golf_scores s
  WHERE s.score_id = p_score_id;

  -- Use the Low Handicap Index established when the previous acceptable
  -- score was processed. It remains in force for the current score.
  SET v_previous_score_date = (
    SELECT h.date_played
    FROM wp_golf_handicap_history h
    WHERE h.player_id = v_player_id
      AND (
           h.date_played < v_date_played
        OR (h.date_played = v_date_played AND h.score_id < p_score_id)
      )
    ORDER BY h.date_played DESC, h.score_id DESC
    LIMIT 1
  );

  SELECT MIN(h.hcp_after)
    INTO v_low_hi
  FROM wp_golf_handicap_history h
  WHERE h.player_id = v_player_id
    AND h.date_played >= DATE_SUB(v_previous_score_date, INTERVAL 1 YEAR)
    AND (
         h.date_played < v_date_played
      OR (h.date_played = v_date_played AND h.score_id < p_score_id)
    );

  UPDATE wp_golf_handicap_history
  SET low_hi_365 = v_low_hi
  WHERE score_id = p_score_id;
END;
-- END_QUERY