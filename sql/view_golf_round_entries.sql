-- view_golf_round_entries
DROP VIEW IF EXISTS `view_golf_round_entries`;

CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_round_entries` AS with base as (
select
    `v`.`score_id` AS `score_id`,
    `v`.`player` AS `player`,
    `v`.`date_played` AS `date_played`,
    `v`.`tee_colour` AS `tee_colour`,
    `v`.`gross_score` AS `gross_score`,
    `v`.`net_score` AS `net_score`,
    `v`.`current_index` AS `current_index`
from
    `view_scoreboard` `v`),
ranked as (
select
    `b`.`score_id` AS `score_id`,
    `b`.`player` AS `player`,
    `b`.`date_played` AS `date_played`,
    `b`.`tee_colour` AS `tee_colour`,
    `b`.`gross_score` AS `gross_score`,
    `b`.`net_score` AS `net_score`,
    `b`.`current_index` AS `current_index`,
    rank() over ( partition by `b`.`date_played`,
    `b`.`tee_colour`
order by
    `b`.`net_score`) AS `nett_position`
from
    `base` `b`),
with_counts as (
select
    `r`.`score_id` AS `score_id`,
    `r`.`player` AS `player`,
    `r`.`date_played` AS `date_played`,
    `r`.`tee_colour` AS `tee_colour`,
    `r`.`gross_score` AS `gross_score`,
    `r`.`net_score` AS `net_score`,
    `r`.`current_index` AS `current_index`,
    `r`.`nett_position` AS `nett_position`,
    sum(case when `r`.`nett_position` = 1 then 1 else 0 end) over ( partition by `r`.`date_played`,
    `r`.`tee_colour`) AS `nett_winners_count`,
    count(0) over ( partition by `r`.`date_played`,
    `r`.`tee_colour`) AS `player_count`
from
    `ranked` `r`
)select
    `wc`.`date_played` AS `date_played`,
    `wc`.`tee_colour` AS `tee_colour`,
    `wc`.`player` AS `player`,
    `wc`.`score_id` AS `score_id`,
    `wc`.`gross_score` AS `gross_score`,
    `wc`.`net_score` AS `net_score`,
    `wc`.`current_index` AS `hcp_index_start`,
    `wc`.`nett_position` AS `nett_position`,
    `wc`.`player_count` AS `player_count`,
    case
        when `wc`.`nett_position` = 1
        and `wc`.`nett_winners_count` > 1 then 1
        else 0
    end AS `is_draw_nett`,
    case
        when `wc`.`nett_position` = 1
        and `wc`.`nett_winners_count` = 1
        and `wc`.`player_count` > 1 then 1
        else 0
    end AS `is_win_nett`
from
    `with_counts` `wc`;

-- END_QUERY
