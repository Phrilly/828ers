DROP VIEW IF EXISTS `view_golf_daily_winners`;
-- END_QUERY

-- WATERMARK 1.0.39
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_daily_winners` AS with DailyRanks as (
select
    `wp_golf_dashboard_history`.`date_played` AS `date_played`,
    `wp_golf_dashboard_history`.`tee_colour` AS `tee_colour`,
    `wp_golf_dashboard_history`.`player_id` AS `player_id`,
    `wp_golf_dashboard_history`.`net_score` AS `net_score`,
    min(`wp_golf_dashboard_history`.`net_score`) over ( partition by `wp_golf_dashboard_history`.`date_played`,
    `wp_golf_dashboard_history`.`tee_colour`) AS `best_score`,
    count(0) over ( partition by `wp_golf_dashboard_history`.`date_played`,
    `wp_golf_dashboard_history`.`tee_colour`) AS `field_size`
from
    `wp_golf_dashboard_history`
where
    `is_excluded` = 0
)select
    `DailyRanks`.`date_played` AS `date_played`,
    `DailyRanks`.`tee_colour` AS `tee_colour`,
    `DailyRanks`.`player_id` AS `winner_id`
from
    `DailyRanks`
where
    `DailyRanks`.`net_score` = `DailyRanks`.`best_score`
    and `DailyRanks`.`field_size` > 1
    and (
    select
        count(0)
    from
        `wp_golf_dashboard_history` `h2`
    where
        `h2`.`date_played` = `DailyRanks`.`date_played`
        and `h2`.`tee_colour` = `DailyRanks`.`tee_colour`
        and `h2`.`is_excluded` = 0
        and `h2`.`net_score` = `DailyRanks`.`best_score`) = 1;
-- END_QUERY