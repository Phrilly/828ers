DROP PROCEDURE IF EXISTS `sp_build_view_golf_rounds_pivot`;
-- END_QUERY

CREATE PROCEDURE `sp_build_view_golf_rounds_pivot`()
BEGIN
  -- WATERMARK 1.0.24
  DECLARE vCols LONGTEXT;

  -- Build pivot columns for all players, using dashboard_history (has playing_hcp)
  SELECT GROUP_CONCAT(
    CONCAT(
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.player_name END) AS `p', p.player_id, '_name`, ',
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.gross_score END) AS `p', p.player_id, '_gross`, ',
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.playing_hcp END) AS `p', p.player_id, '_hcp`, ',
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.net_score END) AS `p', p.player_id, '_net`'
    )
    ORDER BY p.player_id SEPARATOR ', '
  )
  INTO vCols
  FROM wp_golf_players p;

  SET @sql = CONCAT(
    'CREATE OR REPLACE VIEW view_golf_rounds_pivot AS
     SELECT
       r.date_played,
       r.tee_colour,
       CASE WHEN r.winners_count > 1 THEN ''TIE'' ELSE r.winner_player END AS winner,
       '''' AS winner_colour,
       ', vCols, '
     FROM view_golf_rounds r
     LEFT JOIN view_golf_dashboard_history h
       ON h.date_played = r.date_played
      AND h.tee_colour  = r.tee_colour
     GROUP BY r.date_played, r.tee_colour'
  );

  PREPARE stmt FROM @sql;
  EXECUTE stmt;
  DEALLOCATE PREPARE stmt;
END;
-- END_QUERY