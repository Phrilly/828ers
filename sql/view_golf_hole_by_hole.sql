DROP VIEW IF EXISTS `view_golf_hole_by_hole`;
-- END_QUERY

CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_hole_by_hole` AS
SELECT
    `c`.`course_name` AS `course_name`,
    `t`.`tee_colour` AS `tee_colour`,
    `s`.`date_played` AS `date_played`,
    `p`.`name` AS `player_name`,
    `h`.`hole_number` AS `hole_number`,
    `h`.`length` AS `hole_length`,
    `h`.`par` AS `par`,
    `h`.`stroke_index` AS `si`,
    `hs`.`gross_score` AS `gross_score`,
    (FLOOR(COALESCE(`hh`.`playing_hcp`, 0) / 18) +
     CASE
         WHEN (COALESCE(`hh`.`playing_hcp`, 0) % 18) >= `h`.`stroke_index` THEN 1
         ELSE 0
     END) AS `shots`,
    (`hs`.`gross_score` -
     (FLOOR(COALESCE(`hh`.`playing_hcp`, 0) / 18) +
      CASE
          WHEN (COALESCE(`hh`.`playing_hcp`, 0) % 18) >= `h`.`stroke_index` THEN 1
          ELSE 0
      END)) AS `nett_score`,
    GREATEST(
        0,
        (2 + `h`.`par`) -
        (`hs`.`gross_score` -
         (FLOOR(COALESCE(`hh`.`playing_hcp`, 0) / 18) +
          CASE
              WHEN (COALESCE(`hh`.`playing_hcp`, 0) % 18) >= `h`.`stroke_index` THEN 1
              ELSE 0
          END))
    ) AS `stableford_score`,
    `s`.`score_id` AS `score_id`
FROM `wp_golf_hole_scores` `hs`
JOIN `wp_golf_scores` `s`
    ON `hs`.`score_id` = `s`.`score_id`
JOIN `wp_golf_players` `p`
    ON `s`.`player_id` = `p`.`player_id`
JOIN `wp_golf_holes` `h`
    ON `hs`.`hole_number` = `h`.`hole_number`
   AND `s`.`tee_id` = `h`.`tee_id`
JOIN `wp_golf_tees` `t`
    ON `h`.`tee_id` = `t`.`tee_id`
JOIN `wp_golf_courses` `c`
    ON `t`.`course_id` = `c`.`course_id`
LEFT JOIN `wp_golf_handicap_history` `hh`
    ON `s`.`score_id` = `hh`.`score_id`
WHERE `s`.`is_excluded` = 0;

-- END_QUERY