DROP VIEW IF EXISTS `view_golf_player_records`;
-- END_QUERY

-- WATERMARK 1.0.92
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_player_records` AS with rk1 as (
select
    `v`.`score_id` AS `score_id`,
    `v`.`player` AS `player`,
    `v`.`course_name` AS `course_name`,
    `v`.`tee_colour` AS `tee_colour`,
    `v`.`date_played` AS `date_played`,
    `v`.`gross_score` AS `gross_score`,
    `v`.`current_index` AS `current_index`,
    `v`.`playing_handicap` AS `playing_handicap`,
    `v`.`net_score` AS `net_score`,
    `v`.`putts` AS `putts`,
    `v`.`gir` AS `gir`,
    `v`.`pcc_adjustment` AS `pcc_adjustment`,
    `v`.`handicap_differential` AS `handicap_differential`,
    rank() over ( partition by `v`.`date_played`,
    `v`.`tee_colour`
order by
    `v`.`net_score`) AS `nett_rank`,
    count(0) over ( partition by `v`.`date_played`,
    `v`.`tee_colour`) AS `player_count`
from
    `view_scoreboard` `v`),
rk2 as (
select
    `rk1`.`score_id` AS `score_id`,
    `rk1`.`player` AS `player`,
    `rk1`.`course_name` AS `course_name`,
    `rk1`.`tee_colour` AS `tee_colour`,
    `rk1`.`date_played` AS `date_played`,
    `rk1`.`gross_score` AS `gross_score`,
    `rk1`.`current_index` AS `current_index`,
    `rk1`.`playing_handicap` AS `playing_handicap`,
    `rk1`.`net_score` AS `net_score`,
    `rk1`.`putts` AS `putts`,
    `rk1`.`gir` AS `gir`,
    `rk1`.`pcc_adjustment` AS `pcc_adjustment`,
    `rk1`.`handicap_differential` AS `handicap_differential`,
    `rk1`.`nett_rank` AS `nett_rank`,
    `rk1`.`player_count` AS `player_count`,
    sum(case when `rk1`.`nett_rank` = 1 then 1 else 0 end) over ( partition by `rk1`.`date_played`,
    `rk1`.`tee_colour`) AS `rank1_count`
from
    `rk1`),
WinSequence as (
select
    `rk2`.`player` AS `player`,
    `rk2`.`date_played` AS `date_played`,
    `rk2`.`gross_score` AS `gross_score`,
    case
        when `rk2`.`nett_rank` = 1
        and `rk2`.`rank1_count` = 1 
        and `rk2`.`player_count` > 1 then 1 
        else 0
    end AS `is_win`,
    `rk2`.`tee_colour` AS `tee_colour`,
    `rk2`.`score_id` AS `score_id`
from
    `rk2`),
StreakGrouping as (
select
    `ws`.`player` AS `player`,
    `ws`.`is_win` AS `is_win`,
    `ws`.`date_played` AS `date_played`,
    row_number() over ( partition by `ws`.`player`
order by
    `ws`.`date_played`,
    `ws`.`tee_colour`,
    `ws`.`score_id`) - row_number() over ( partition by `ws`.`player`,
    `ws`.`is_win`
order by
    `ws`.`date_played`,
    `ws`.`tee_colour`,
    `ws`.`score_id`) AS `grp`
from
    `WinSequence` `ws`),
StreakStats as (
select
    `sg`.`player` AS `player`,
    `sg`.`grp` AS `grp`,
    count(0) AS `streak_length`,
    min(`sg`.`date_played`) AS `start_date`,
    max(`sg`.`date_played`) AS `end_date`
from
    `StreakGrouping` `sg`
where
    `sg`.`is_win` = 1
group by
    `sg`.`player`,
    `sg`.`grp`),
LongestStreakPerPlayer as (
select
    `ss`.`player` AS `player`,
    `ss`.`streak_length` AS `streak_length`,
    `ss`.`start_date` AS `start_date`,
    `ss`.`end_date` AS `end_date`,
    row_number() over ( partition by `ss`.`player`
order by
    `ss`.`streak_length` desc,
    `ss`.`end_date` desc) AS `streak_rank`
from
    `StreakStats` `ss`),
LowestScoreRank as (
select
    `p`.`name` AS `player_name`,
    `p`.`initials` AS `player_initials`,
    `s`.`gross_score` AS `gross_score`,
    `s`.`date_played` AS `date_played`,
    row_number() over ( partition by `p`.`player_id`
order by
    `s`.`gross_score`,
    `s`.`date_played` desc) AS `score_rank`
from
    (`wp_golf_scores` `s`
join `wp_golf_players` `p` on
    (`s`.`player_id` = `p`.`player_id`))
where
    `s`.`is_excluded` = 0
)select
    `p`.`player_id` AS `player_id`,
    `p`.`name` AS `player_name`,
    `lsr`.`gross_score` AS `best_score`,
    `lsr`.`date_played` AS `best_date`,
    coalesce(`lsp`.`streak_length`, 0) AS `streak_count`,
    `lsp`.`start_date` AS `streak_start`,
    `lsp`.`end_date` AS `streak_end`
from
    ((`wp_golf_players` `p`
left join `LowestScoreRank` `lsr` on
    (`p`.`name` = `lsr`.`player_name` and `lsr`.`score_rank` = 1))
left join `LongestStreakPerPlayer` `lsp` on
    (`p`.`name` = `lsp`.`player` and `lsp`.`streak_rank` = 1));
-- END_QUERY