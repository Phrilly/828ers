DROP VIEW IF EXISTS `view_golf_dashboard_history`;
-- END_QUERY

-- WATERMARK 1.0.53
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_dashboard_history` AS
select
    `s`.`score_id` AS `score_id`,
    `p`.`player_id` AS `player_id`,
    `p`.`name` AS `player_name`,
    `s`.`date_played` AS `date_played`,
    `t`.`tee_colour` AS `tee_colour`,
    `s`.`gross_score` AS `gross_score`,
    `s`.`putts` AS `putts`,
    `s`.`gir` AS `gir`,
    `h`.`hcp_before` AS `starting_index`,
    `h`.`playing_hcp` AS `playing_hcp`,
    `h`.`net_score` AS `net_score`,
    `h`.`differential` AS `differential`,
    `h`.`is_best_8` AS `is_counting`,
    case
        when `h`.`cap_type` is not null
        and `h`.`cap_type` <> 'NONE' then 1
        else 0
    end AS `cap_applied`,
    case
        when `h`.`esr_triggered` = 1 then 1
        else 0
    end AS `esr_applied`,
    `h`.`cap_type` AS `cap_type`,
    `h`.`cap_reduction` AS `cap_reduction`,
    `h`.`esr_triggered` AS `esr_triggered`,
    `h`.`esr_amount` AS `esr_amount`,
    `h`.`esr_adj` AS `esr_adj`,
    trim(concat(case when `h`.`esr_triggered` = 1 then 'ESR ' else '' end, case when `h`.`cap_type` is not null and `h`.`cap_type` <> 'NONE' then `h`.`cap_type` else '' end)) AS `adj_flag`
from
    (((`wp_golf_scores` `s`
join `wp_golf_players` `p` on
    (`p`.`player_id` = `s`.`player_id`))
join `wp_golf_tees` `t` on
    (`t`.`tee_id` = `s`.`tee_id`))
left join `wp_golf_handicap_history` `h` on
    (`h`.`score_id` = `s`.`score_id`)) where `s`.`is_excluded` = 0;
-- END_QUERY