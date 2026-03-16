DROP VIEW IF EXISTS `view_golf_rolling_averages`;
-- END_QUERY

-- WATERMARK 1.0.33
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_rolling_averages` AS
select
    `ranked_history`.`player_id` AS `player_id`,
    `ranked_history`.`player_name` AS `player_name`,
    round(avg(`ranked_history`.`putts`), 1) AS `avg_putts_20`,
    round(avg(`ranked_history`.`gir`), 1) AS `avg_gir_20`
from
    (
    select
        `wp_golf_dashboard_history`.`player_id` AS `player_id`,
        `wp_golf_dashboard_history`.`player_name` AS `player_name`,
        `wp_golf_dashboard_history`.`putts` AS `putts`,
        `wp_golf_dashboard_history`.`gir` AS `gir`,
        row_number() over ( partition by `wp_golf_dashboard_history`.`player_id`
    order by
        `wp_golf_dashboard_history`.`date_played` desc) AS `row_num`
    from
        `wp_golf_dashboard_history`) `ranked_history`
where
    `ranked_history`.`row_num` <= 20
group by
    `ranked_history`.`player_id`,
    `ranked_history`.`player_name`;
-- END_QUERY