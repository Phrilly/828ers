DROP VIEW IF EXISTS `view_playing_handicaps`;
-- END_QUERY

-- WATERMARK 1.0.62
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_playing_handicaps` AS
SELECT
    `vhi`.`player_id`,
    `vhi`.`player_name`,
    /* White Tee Integer Trend */
    CASE 
        WHEN ROUND((`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95, 0) < 
             ROUND((`vhi`.`previous_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95, 0) THEN 'down'
        WHEN ROUND((`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95, 0) > 
             ROUND((`vhi`.`previous_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95, 0) THEN 'up'
        ELSE 'same'
    END AS `white_direction`,
    ROUND(`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`), 2) AS `white_exact`,
    ROUND((`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95, 0) AS `white_play`,

    /* Yellow Tee Integer Trend */
    CASE 
        WHEN ROUND((`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95, 0) < 
             ROUND((`vhi`.`previous_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95, 0) THEN 'down'
        WHEN ROUND((`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95, 0) > 
             ROUND((`vhi`.`previous_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95, 0) THEN 'up'
        ELSE 'same'
    END AS `yellow_direction`,
    ROUND(`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`), 2) AS `yellow_exact`,
    ROUND((`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95, 0) AS `yellow_play`,

    /* Black Tee Integer Trend */
    CASE 
        WHEN ROUND((`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95, 0) < 
             ROUND((`vhi`.`previous_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95, 0) THEN 'down'
        WHEN ROUND((`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95, 0) > 
             ROUND((`vhi`.`previous_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95, 0) THEN 'up'
        ELSE 'same'
    END AS `black_direction`,
    ROUND(`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`), 2) AS `black_exact`,
    ROUND((`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95, 0) AS `black_play`
FROM
    ((((`view_handicap_index` `vhi`
LEFT JOIN `wp_golf_tees` `tw` ON (`tw`.`tee_colour` = 'White'))
LEFT JOIN `wp_golf_tees` `ty` ON (`ty`.`tee_colour` = 'Yellow'))
LEFT JOIN `wp_golf_tees` `tb` ON (`tb`.`tee_colour` = 'Black'))
JOIN `wp_golf_courses` `c` ON (`c`.`course_name` = 'Ramsey Golf Club'))
WHERE
    `tw`.`course_id` = `c`.`course_id` AND `ty`.`course_id` = `c`.`course_id` AND `tb`.`course_id` = `c`.`course_id`;
-- END_QUERY