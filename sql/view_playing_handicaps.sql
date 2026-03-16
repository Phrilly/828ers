-- view_playing_handicaps
DROP VIEW IF EXISTS `view_playing_handicaps`;

CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_playing_handicaps` AS
select
    `vhi`.`player_id` AS `player_id`,
    `vhi`.`player_name` AS `player_name`,
    round(`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`), 2) AS `white_exact`,
    round((`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95, 0) AS `white_play`,
    round(`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`), 2) AS `yellow_exact`,
    round((`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95, 0) AS `yellow_play`,
    round(`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`), 2) AS `black_exact`,
    round((`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95, 0) AS `black_play`
from
    ((((`view_handicap_index` `vhi`
left join `wp_golf_tees` `tw` on
    (`tw`.`tee_colour` = 'White'))
left join `wp_golf_tees` `ty` on
    (`ty`.`tee_colour` = 'Yellow'))
left join `wp_golf_tees` `tb` on
    (`tb`.`tee_colour` = 'Black'))
join `wp_golf_courses` `c` on
    (`c`.`course_name` = 'Ramsey Golf Club'))
where
    `tw`.`course_id` = `c`.`course_id`
    and `ty`.`course_id` = `c`.`course_id`
    and `tb`.`course_id` = `c`.`course_id`;

-- END_QUERY
