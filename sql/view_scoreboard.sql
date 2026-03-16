-- view_scoreboard
DROP VIEW IF EXISTS `view_scoreboard`;

CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_scoreboard` AS
select
    `s`.`score_id` AS `score_id`,
    `p`.`name` AS `player`,
    `c`.`course_name` AS `course_name`,
    `t`.`tee_colour` AS `tee_colour`,
    `s`.`date_played` AS `date_played`,
    `s`.`gross_score` AS `gross_score`,
    coalesce(`hh`.`hcp_before`, 54.0) AS `current_index`,
    `hh`.`playing_hcp` AS `playing_handicap`,
    `hh`.`net_score` AS `net_score`,
    `s`.`putts` AS `putts`,
    `s`.`gir` AS `gir`,
    `s`.`pcc_adjustment` AS `pcc_adjustment`,
    `hh`.`differential` AS `handicap_differential`
from
    ((((`wp_golf_scores` `s`
join `wp_golf_players` `p` on
    (`s`.`player_id` = `p`.`player_id`))
join `wp_golf_tees` `t` on
    (`t`.`tee_id` = `s`.`tee_id`))
join `wp_golf_courses` `c` on
    (`t`.`course_id` = `c`.`course_id`))
left join `wp_golf_handicap_history` `hh` on
    (`hh`.`score_id` = `s`.`score_id`))
order by
    `s`.`date_played` desc;

-- END_QUERY
