DROP VIEW IF EXISTS `view_golf_win_streaks`;
-- END_QUERY

-- WATERMARK 1.0.82
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_win_streaks` AS with rounds as (
select
    `e`.`player` AS `player`,
    `e`.`date_played` AS `date_played`,
    `e`.`tee_colour` AS `tee_colour`,
    `e`.`score_id` AS `score_id`,
    `e`.`is_win_nett` AS `is_win_nett`,
    sum(case when `e`.`is_win_nett` = 0 then 1 else 0 end) over ( partition by `e`.`player`
order by
    `e`.`date_played`,
    `e`.`tee_colour`,
    `e`.`score_id` rows between unbounded preceding and current row ) AS `break_grp`
from
    `view_golf_round_entries` `e`)
where
    `e`.`player_count` > 1),
wins as (
select
    `r`.`player` AS `player`,
    `r`.`break_grp` AS `break_grp`,
    count(0) AS `streak_wins`,
    min(`r`.`score_id`) AS `first_score_id`,
    max(`r`.`score_id`) AS `last_score_id`
from
    `rounds` `r`
where
    `r`.`is_win_nett` = 1
group by
    `r`.`player`,
    `r`.`break_grp`
)select
    `w`.`player` AS `player`,
    `s1`.`date_played` AS `streak_start_date`,
    `s1`.`tee_colour` AS `streak_start_tee`,
    `s2`.`date_played` AS `streak_end_date`,
    `s2`.`tee_colour` AS `streak_end_tee`,
    `w`.`streak_wins` AS `streak_wins`,
    `w`.`first_score_id` AS `first_score_id`,
    `w`.`last_score_id` AS `last_score_id`
from
    ((`wins` `w`
join `view_golf_round_entries` `s1` on
    (`s1`.`score_id` = `w`.`first_score_id`))
join `view_golf_round_entries` `s2` on
    (`s2`.`score_id` = `w`.`last_score_id`));
-- END_QUERY