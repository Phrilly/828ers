DROP VIEW IF EXISTS `view_golf_dashboard_history`;
-- END_QUERY

-- WATERMARK 1.0.65
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_dashboard_history` AS
SELECT
    `s`.`score_id` AS `score_id`,
    `p`.`player_id` AS `player_id`,
    `p`.`name` AS `player_name`,
    `s`.`date_played` AS `date_played`,
    `t`.`tee_colour` AS `tee_colour`,
    `s`.`gross_score` AS `gross_score`,
    `s`.`putts` AS `putts`,
    `s`.`gir` AS `gir`,
    `s`.`pcc_adjustment` AS `pcc`,
    `h`.`hcp_before` AS `starting_index`,
    `h`.`low_hi_365` AS `low_hi_365`,
    `h`.`playing_hcp` AS `playing_hcp`,
    `h`.`net_score` AS `net_score`,
    `h`.`differential` AS `differential`,
    `h`.`is_best_8` AS `is_counting`,
    CASE
        WHEN `h`.`cap_type` IS NOT NULL AND `h`.`cap_type` <> 'NONE' THEN 1
        ELSE 0
    END AS `cap_applied`,
    CASE
        WHEN `h`.`esr_triggered` = 1 THEN 1
        ELSE 0
    END AS `esr_applied`,
    `h`.`cap_type` AS `cap_type`,
    `h`.`cap_reduction` AS `cap_reduction`,
    `h`.`esr_triggered` AS `esr_triggered`,
    `h`.`esr_amount` AS `esr_amount`,
    `h`.`esr_adj` AS `esr_adj`,
    TRIM(CONCAT(
        CASE WHEN `h`.`esr_triggered` = 1 THEN 'ESR ' ELSE '' END,
        CASE WHEN `h`.`cap_type` IS NOT NULL AND `h`.`cap_type` <> 'NONE' THEN `h`.`cap_type` ELSE '' END
    )) AS `adj_flag`
FROM
    (((`wp_golf_scores` `s`
JOIN `wp_golf_players` `p` ON (`p`.`player_id` = `s`.`player_id`))
JOIN `wp_golf_tees` `t` ON (`t`.`tee_id` = `s`.`tee_id`))
LEFT JOIN `wp_golf_handicap_history` `h` ON (`h`.`score_id` = `s`.`score_id`))
WHERE `s`.`is_excluded` = 0;
-- END_QUERY
