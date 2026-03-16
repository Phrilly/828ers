-- view_golf_players_pivot_names
DROP VIEW IF EXISTS `view_golf_players_pivot_names`;

CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_players_pivot_names` AS
select
    max(case when `p`.`player_id` = 1 then `p`.`name` end) AS `p1_name`,
    max(case when `p`.`player_id` = 2 then `p`.`name` end) AS `p2_name`,
    max(case when `p`.`player_id` = 3 then `p`.`name` end) AS `p3_name`,
    max(case when `p`.`player_id` = 4 then `p`.`name` end) AS `p4_name`
from
    `wp_golf_players` `p`;

-- END_QUERY
