DROP VIEW IF EXISTS `view_golf_win_streaks`;
-- END_QUERY

-- WATERMARK 1.0.95
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_win_streaks` AS 
WITH rounds AS (
    SELECT
        `e`.`player` AS `player`,
        `e`.`date_played` AS `date_played`,
        `e`.`tee_colour` AS `tee_colour`,
        `e`.`score_id` AS `score_id`,
        `e`.`is_win_nett` AS `is_win_nett`,
        SUM(CASE WHEN `e`.`is_win_nett` = 0 THEN 1 ELSE 0 END) OVER (
            PARTITION BY `e`.`player`
            ORDER BY `e`.`date_played`, `e`.`tee_colour`, `e`.`score_id` 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS `break_grp`
    FROM
        `view_golf_round_entries` `e`
),
wins AS (
    SELECT
        `r`.`player` AS `player`,
        `r`.`break_grp` AS `break_grp`,
        COUNT(0) AS `streak_wins`,
        MIN(`r`.`score_id`) AS `first_score_id`,
        MAX(`r`.`score_id`) AS `last_score_id`
    FROM
        `rounds` `r`
    WHERE
        `r`.`is_win_nett` = 1
    GROUP BY
        `r`.`player`,
        `r`.`break_grp`
)
SELECT
    `w`.`player` AS `player`,
    `s1`.`date_played` AS `streak_start_date`,
    `s1`.`tee_colour` AS `streak_start_tee`,
    `s2`.`date_played` AS `streak_end_date`,
    `s2`.`tee_colour` AS `streak_end_tee`,
    `w`.`streak_wins` AS `streak_wins`,
    `w`.`first_score_id` AS `first_score_id`,
    `w`.`last_score_id` AS `last_score_id`
FROM
    `wins` `w`
JOIN `view_golf_round_entries` `s1` ON (`s1`.`score_id` = `w`.`first_score_id`)
JOIN `view_golf_round_entries` `s2` ON (`s2`.`score_id` = `w`.`last_score_id`);
-- END_QUERY