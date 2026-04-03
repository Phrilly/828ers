DROP VIEW IF EXISTS `view_golf_rolling_averages`;
-- END_QUERY

-- WATERMARK 1.0.61
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_rolling_averages` AS
SELECT
    `ranked_history`.`player_id` AS `player_id`,
    `ranked_history`.`player_name` AS `player_name`,
    
    /* Removed the trailing comma from the line below */
    ROUND(AVG(CASE WHEN `ranked_history`.`putts` > 0 THEN `ranked_history`.`putts` ELSE NULL END), 1) AS `avg_putts_20`, 
    ROUND(AVG(CASE WHEN `ranked_history`.`putts` > 0 THEN `ranked_history`.`gir` ELSE NULL END), 1) AS `avg_gir_20`
FROM
    (
    SELECT
        `view_golf_dashboard_history`.`player_id` AS `player_id`,
        `view_golf_dashboard_history`.`player_name` AS `player_name`,
        `view_golf_dashboard_history`.`putts` AS `putts`,
        `view_golf_dashboard_history`.`gir` AS `gir`,
        ROW_NUMBER() OVER (
            PARTITION BY `view_golf_dashboard_history`.`player_id`
            ORDER BY `view_golf_dashboard_history`.`date_played` DESC
        ) AS `row_num`
    FROM
        `view_golf_dashboard_history`
    ) AS `ranked_history`
WHERE
    `ranked_history`.`row_num` <= 20
GROUP BY
    `ranked_history`.`player_id`,
    `ranked_history`.`player_name`;
-- END_QUERY