-- --------------------------------------------------------
-- 828ers GOLF SYSTEM: VIEWS
-- --------------------------------------------------------

CREATE OR REPLACE VIEW `view_best_8_rounds` AS 
SELECT `v20`.`player_id` AS `player_id`, `v20`.`score_id` AS `score_id`, `v20`.`differential` AS `differential` 
FROM `view_last_20_rounds` AS `v20` 
WHERE (SELECT COUNT(0) FROM `view_last_20_rounds` `vComp` WHERE `vComp`.`player_id` = `v20`.`player_id` AND (`vComp`.`differential` < `v20`.`differential` OR `vComp`.`differential` = `v20`.`differential` AND `vComp`.`score_id` <= `v20`.`score_id`)) <= 8;
-- END_QUERY

CREATE OR REPLACE VIEW `view_golf_daily_winners` AS 
WITH DailyRanks AS (
    SELECT `wp_golf_dashboard_history`.`date_played`, `wp_golf_dashboard_history`.`tee_colour`, `wp_golf_dashboard_history`.`player_id`, `wp_golf_dashboard_history`.`net_score`, 
    MIN(`wp_golf_dashboard_history`.`net_score`) OVER (PARTITION BY `wp_golf_dashboard_history`.`date_played`,`wp_golf_dashboard_history`.`tee_colour`) AS `best_score`, 
    COUNT(0) OVER (PARTITION BY `wp_golf_dashboard_history`.`date_played`,`wp_golf_dashboard_history`.`tee_colour`) AS `field_size` 
    FROM `wp_golf_dashboard_history`
) 
SELECT `DailyRanks`.`date_played`, `DailyRanks`.`tee_colour`, `DailyRanks`.`player_id` AS `winner_id` 
FROM `DailyRanks` 
WHERE `DailyRanks`.`net_score` = `DailyRanks`.`best_score` AND `DailyRanks`.`field_size` > 1 
AND (SELECT COUNT(0) FROM `wp_golf_dashboard_history` `h2` WHERE `h2`.`date_played` = `DailyRanks`.`date_played` AND `h2`.`tee_colour` = `DailyRanks`.`tee_colour` AND `h2`.`net_score` = `DailyRanks`.`best_score`) = 1;
-- END_QUERY

CREATE OR REPLACE VIEW `view_golf_dashboard_history` AS 
SELECT `s`.`score_id`, `p`.`name` AS `player_name`, `s`.`date_played`, `t`.`tee_colour`, `s`.`gross_score`, `h`.`hcp_before` AS `starting_index`, `h`.`playing_hcp`, `h`.`net_score`, `h`.`differential`, `h`.`is_best_8` AS `is_counting`, 
CASE WHEN `h`.`cap_type` IS NOT NULL AND `h`.`cap_type` <> 'NONE' THEN 1 ELSE 0 END AS `cap_applied`, 
CASE WHEN `h`.`esr_triggered` = 1 THEN 1 ELSE 0 END AS `esr_applied`, `h`.`cap_type`, `h`.`cap_reduction`, `h`.`esr_triggered`, `h`.`esr_amount`, `h`.`esr_adj`, 
TRIM(CONCAT(CASE WHEN `h`.`esr_triggered` = 1 THEN 'ESR ' ELSE '' END, CASE WHEN `h`.`cap_type` IS NOT NULL AND `h`.`cap_type` <> 'NONE' THEN `h`.`cap_type` ELSE '' END)) AS `adj_flag` 
FROM (((`wp_golf_scores` `s` JOIN `wp_golf_players` `p` ON(`p`.`player_id` = `s`.`player_id`)) JOIN `wp_golf_tees` `t` ON(`t`.`tee_id` = `s`.`tee_id`)) LEFT JOIN `wp_golf_handicap_history` `h` ON(`h`.`score_id` = `s`.`score_id`));
-- END_QUERY

CREATE OR REPLACE VIEW `view_golf_players_pivot_names` AS 
SELECT MAX(CASE WHEN `p`.`player_id` = 1 THEN `p`.`name` END) AS `p1_name`, 
MAX(CASE WHEN `p`.`player_id` = 2 THEN `p`.`name` END) AS `p2_name`, 
MAX(CASE WHEN `p`.`player_id` = 3 THEN `p`.`name` END) AS `p3_name`, 
MAX(CASE WHEN `p`.`player_id` = 4 THEN `p`.`name` END) AS `p4_name` 
FROM `wp_golf_players` AS `p`;
-- END_QUERY

CREATE OR REPLACE VIEW `view_golf_rolling_averages` AS 
SELECT `ranked_history`.`player_id`, `ranked_history`.`player_name`, ROUND(AVG(`ranked_history`.`putts`),1) AS `avg_putts_20`, ROUND(AVG(`ranked_history`.`gir`),1) AS `avg_gir_20` 
FROM (SELECT `player_id`, `player_name`, `putts`, `gir`, ROW_NUMBER() OVER (PARTITION BY `player_id` ORDER BY `date_played` DESC) AS `row_num` FROM `wp_golf_dashboard_history`) AS `ranked_history` 
WHERE `ranked_history`.`row_num` <= 20 
GROUP BY `ranked_history`.`player_id`, `ranked_history`.`player_name`;
-- END_QUERY

CREATE OR REPLACE VIEW `view_golf_rounds` AS 
SELECT `e`.`date_played`, `e`.`tee_colour`, MAX(`e`.`player_count`) AS `player_count`, MIN(`e`.`net_score`) AS `best_nett_score`, SUM(CASE WHEN `e`.`nett_position` = 1 THEN 1 ELSE 0 END) AS `winners_count`, 
CASE WHEN SUM(CASE WHEN `e`.`nett_position` = 1 THEN 1 ELSE 0 END) = 1 THEN MAX(CASE WHEN `e`.`nett_position` = 1 THEN `e`.`player` END) ELSE NULL END AS `winner_player`, 
CASE WHEN SUM(CASE WHEN `e`.`nett_position` = 1 THEN 1 ELSE 0 END) = 1 THEN MAX(CASE WHEN `e`.`nett_position` = 1 THEN `p`.`winner_colour` END) ELSE NULL END AS `winner_colour` 
FROM (`view_golf_round_entries` `e` LEFT JOIN `wp_golf_players` `p` ON(`p`.`name` = `e`.`player`)) 
GROUP BY `e`.`date_played`, `e`.`tee_colour`;
-- END_QUERY

CREATE OR REPLACE VIEW `view_golf_round_entries` AS 
WITH base AS (
    SELECT `v`.`score_id`, `v`.`player`, `v`.`date_played`, `v`.`tee_colour`, `v`.`gross_score`, `v`.`net_score`, `v`.`current_index` FROM `view_scoreboard` AS `v`
), ranked AS (
    SELECT `b`.*, RANK() OVER (PARTITION BY `b`.`date_played`,`b`.`tee_colour` ORDER BY `b`.`net_score`) AS `nett_position` FROM `base` AS `b`
), with_counts AS (
    SELECT `r`.*, SUM(CASE WHEN `r`.`nett_position` = 1 THEN 1 ELSE 0 END) OVER (PARTITION BY `r`.`date_played`,`r`.`tee_colour`) AS `nett_winners_count`, 
    COUNT(0) OVER (PARTITION BY `r`.`date_played`,`r`.`tee_colour`) AS `player_count` FROM `ranked` AS `r`
) 
SELECT `wc`.`date_played`, `wc`.`tee_colour`, `wc`.`player`, `wc`.`score_id`, `wc`.`gross_score`, `wc`.`net_score`, `wc`.`current_index` AS `hcp_index_start`, `wc`.`nett_position`, `wc`.`player_count`, 
CASE WHEN `wc`.`nett_position` = 1 AND `wc`.`nett_winners_count` > 1 THEN 1 ELSE 0 END AS `is_draw_nett`, 
CASE WHEN `wc`.`nett_position` = 1 AND `wc`.`nett_winners_count` = 1 AND `wc`.`player_count` > 1 THEN 1 ELSE 0 END AS `is_win_nett` 
FROM `with_counts` AS `wc`;
-- END_QUERY

CREATE OR REPLACE VIEW `view_golf_win_streaks` AS 
WITH rounds AS (
    SELECT `e`.`player`, `e`.`date_played`, `e`.`tee_colour`, `e`.`score_id`, `e`.`is_win_nett`, 
    SUM(CASE WHEN `e`.`is_win_nett` = 0 THEN 1 ELSE 0 END) OVER (PARTITION BY `e`.`player` ORDER BY `e`.`date_played`,`e`.`tee_colour`,`e`.`score_id` ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS `break_grp` 
    FROM `view_golf_round_entries` AS `e`
), wins AS (
    SELECT `r`.`player`, `r`.`break_grp`, COUNT(0) AS `streak_wins`, MIN(`r`.`score_id`) AS `first_score_id`, MAX(`r`.`score_id`) AS `last_score_id` 
    FROM `rounds` AS `r` WHERE `r`.`is_win_nett` = 1 GROUP BY `r`.`player`, `r`.`break_grp`
) 
SELECT `w`.`player`, `s1`.`date_played` AS `streak_start_date`, `s1`.`tee_colour` AS `streak_start_tee`, `s2`.`date_played` AS `streak_end_date`, `s2`.`tee_colour` AS `streak_end_tee`, `w`.`streak_wins`, `w`.`first_score_id`, `w`.`last_score_id` 
FROM ((`wins` `w` JOIN `view_golf_round_entries` `s1` ON(`s1`.`score_id` = `w`.`first_score_id`)) JOIN `view_golf_round_entries` `s2` ON(`s2`.`score_id` = `w`.`last_score_id`));
-- END_QUERY

CREATE OR REPLACE VIEW `view_last_20_rounds` AS 
SELECT `view_round_differentials`.`player_id`, `view_round_differentials`.`score_id`, `view_round_differentials`.`differential` 
FROM `view_round_differentials` WHERE `view_round_differentials`.`recency_rank` <= 20;
-- END_QUERY

CREATE OR REPLACE VIEW `view_playing_handicaps` AS 
SELECT `vhi`.`player_id`, `vhi`.`player_name`, 
ROUND(`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`),2) AS `white_exact`, 
ROUND((`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95,0) AS `white_play`, 
ROUND(`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`),2) AS `yellow_exact`, 
ROUND((`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95,0) AS `yellow_play`, 
ROUND(`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`),2) AS `black_exact`, 
ROUND((`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95,0) AS `black_play` 
FROM ((((`view_handicap_index` `vhi` LEFT JOIN `wp_golf_tees` `tw` ON(`tw`.`tee_colour` = 'White')) LEFT JOIN `wp_golf_tees` `ty` ON(`ty`.`tee_colour` = 'Yellow')) LEFT JOIN `wp_golf_tees` `tb` ON(`tb`.`tee_colour` = 'Black')) JOIN `wp_golf_courses` `c` ON(`c`.`course_name` = 'Ramsey Golf Club')) 
WHERE `tw`.`course_id` = `c`.`course_id` AND `ty`.`course_id` = `c`.`course_id` AND `tb`.`course_id` = `c`.`course_id`;
-- END_QUERY

CREATE OR REPLACE VIEW `view_round_differentials` AS 
SELECT `s`.`player_id`, `s`.`score_id`, `s`.`date_played`, `s`.`gross_score`, ROUND((`s`.`gross_score` - `t`.`course_rating` - COALESCE(`s`.`pcc_adjustment`,0)) * 113 / `t`.`slope_rating`,1) AS `differential`, 
(SELECT COUNT(0) + 1 FROM `wp_golf_scores` `s2` WHERE `s2`.`player_id` = `s`.`player_id` AND `s2`.`is_excluded` = 0 AND (`s2`.`date_played` > `s`.`date_played` OR `s2`.`date_played` = `s`.`date_played` AND `s2`.`score_id` > `s`.`score_id`)) AS `recency_rank` 
FROM (`wp_golf_scores` `s` JOIN `wp_golf_tees` `t` ON(`s`.`tee_id` = `t`.`tee_id`)) WHERE `s`.`is_excluded` = 0;
-- END_QUERY

CREATE OR REPLACE VIEW `view_scoreboard` AS 
SELECT `s`.`score_id`, `p`.`name` AS `player`, `c`.`course_name`, `t`.`tee_colour`, `s`.`date_played`, `s`.`gross_score`, COALESCE(`hh`.`hcp_before`,54.0) AS `current_index`, `hh`.`playing_hcp` AS `playing_handicap`, `hh`.`net_score` AS `net_score`, `s`.`putts`, `s`.`gir`, `s`.`pcc_adjustment`, `hh`.`differential` AS `handicap_differential` 
FROM ((((`wp_golf_scores` `s` JOIN `wp_golf_players` `p` ON(`s`.`player_id` = `p`.`player_id`)) JOIN `wp_golf_tees` `t` ON(`t`.`tee_id` = `s`.`tee_id`)) JOIN `wp_golf_courses` `c` ON(`t`.`course_id` = `c`.`course_id`)) LEFT JOIN `wp_golf_handicap_history` `hh` ON(`hh`.`score_id` = `s`.`score_id`)) 
ORDER BY `s`.`date_played` DESC;
-- END_QUERY

CREATE OR REPLACE VIEW `wp_golf_dashboard_history` AS 
SELECT `s`.`score_id`, `s`.`date_played`, `s`.`player_id`, `p`.`name` AS `player_name`, `s`.`tee_id`, `t`.`tee_colour`, `s`.`gross_score`, `s`.`pcc_adjustment`, `h`.`hcp_before` AS `index`, `h`.`hcp_before` AS `starting_index`, `h`.`playing_hcp`, `h`.`net_score`, `h`.`differential`, `s`.`putts`, `s`.`gir`, `h`.`is_best_8` AS `is_counting`, 
CASE WHEN `h`.`cap_type` IS NOT NULL AND `h`.`cap_type` <> 'NONE' THEN 1 ELSE 0 END AS `cap_applied`, 
CASE WHEN `h`.`esr_triggered` = 1 THEN 1 ELSE 0 END AS `esr_applied`, `h`.`cap_type`, `h`.`cap_reduction`, `h`.`esr_triggered`, `h`.`esr_amount`, `s`.`is_excluded` 
FROM (((`wp_golf_scores` `s` JOIN `wp_golf_players` `p` ON(`p`.`player_id` = `s`.`player_id`)) JOIN `wp_golf_tees` `t` ON(`t`.`tee_id` = `s`.`tee_id`)) LEFT JOIN `wp_golf_handicap_history` `h` ON(`h`.`score_id` = `s`.`score_id`));
-- END_QUERY