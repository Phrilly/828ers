DROP VIEW IF EXISTS `view_golf_rolling_averages`;
-- END_QUERY

-- WATERMARK 1.0.33
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_rolling_averages` AS
select
    `ranked_history`.`player_id` AS `player_id`,
    `ranked_history`.`player_name` AS `player_name`,
    
    /* Logic: If putts is 0, treat as NULL so it's ignored by the AVG function */
    ROUND(AVG(CASE WHEN putts > 0 THEN putts ELSE NULL END), 1) AS avg_putts_20, 
    ROUND(AVG(CASE WHEN putts > 0 THEN gir ELSE NULL END), 1) AS avg_gir_20,
from
    (
    select
        `view_golf_dashboard_history`.`player_id` AS `player_id`,
        `view_golf_dashboard_history`.`player_name` AS `player_name`,
        `view_golf_dashboard_history`.`putts` AS `putts`,
        `view_golf_dashboard_history`.`gir` AS `gir`,
        row_number() over ( partition by `view_golf_dashboard_history`.`player_id`
    order by
        `view_golf_dashboard_history`.`date_played` desc) AS `row_num`
    from
        `view_golf_dashboard_history`) `ranked_history`
where
    `ranked_history`.`row_num` <= 20
group by
    `ranked_history`.`player_id`,
    `ranked_history`.`player_name`;
-- END_QUERY