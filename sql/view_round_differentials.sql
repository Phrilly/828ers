DROP VIEW IF EXISTS `view_round_differentials`;
-- END_QUERY

-- WATERMARK 1.0.33
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_round_differentials` AS
select
    `s`.`player_id` AS `player_id`,
    `s`.`score_id` AS `score_id`,
    `s`.`date_played` AS `date_played`,
    `s`.`gross_score` AS `gross_score`,
    round((`s`.`gross_score` - `t`.`course_rating` - coalesce(`s`.`pcc_adjustment`, 0)) * 113 / `t`.`slope_rating`, 1) AS `differential`,
    (
    select
        count(0) + 1
    from
        `wp_golf_scores` `s2`
    where
        `s2`.`player_id` = `s`.`player_id`
        and `s2`.`is_excluded` = 0
        and (`s2`.`date_played` > `s`.`date_played`
            or `s2`.`date_played` = `s`.`date_played`
            and `s2`.`score_id` > `s`.`score_id`)) AS `recency_rank`
from
    (`wp_golf_scores` `s`
join `wp_golf_tees` `t` on
    (`s`.`tee_id` = `t`.`tee_id`))
where
    `s`.`is_excluded` = 0;
-- END_QUERY