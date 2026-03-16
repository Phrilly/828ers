DROP VIEW IF EXISTS `view_golf_rounds_pivot`;
-- END_QUERY

-- WATERMARK 1.0.33
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_rounds_pivot` AS
select
    `r`.`date_played` AS `date_played`,
    `r`.`tee_colour` AS `tee_colour`,
    case
        when `r`.`player_count` < 2 then NULL
        when `r`.`winners_count` > 1 then 'TIE'
        else `r`.`winner_player`
    end AS `winner`,
    case
        when `r`.`player_count` < 2 then NULL
        when `r`.`winners_count` > 1 then NULL
        else `r`.`winner_colour`
    end AS `winner_colour`,
    max(case when `h`.`player_id` = 1 then `h`.`player_name` end) AS `p1_name`,
    max(case when `h`.`player_id` = 1 then `p`.`winner_colour` end) AS `p1_colour`,
    max(case when `h`.`player_id` = 1 then `h`.`gross_score` end) AS `p1_gross`,
    max(case when `h`.`player_id` = 1 then `h`.`playing_hcp` end) AS `p1_hcp`,
    max(case when `h`.`player_id` = 1 then `h`.`net_score` end) AS `p1_net`,
    max(case when `h`.`player_id` = 2 then `h`.`player_name` end) AS `p2_name`,
    max(case when `h`.`player_id` = 2 then `p`.`winner_colour` end) AS `p2_colour`,
    max(case when `h`.`player_id` = 2 then `h`.`gross_score` end) AS `p2_gross`,
    max(case when `h`.`player_id` = 2 then `h`.`playing_hcp` end) AS `p2_hcp`,
    max(case when `h`.`player_id` = 2 then `h`.`net_score` end) AS `p2_net`,
    max(case when `h`.`player_id` = 3 then `h`.`player_name` end) AS `p3_name`,
    max(case when `h`.`player_id` = 3 then `p`.`winner_colour` end) AS `p3_colour`,
    max(case when `h`.`player_id` = 3 then `h`.`gross_score` end) AS `p3_gross`,
    max(case when `h`.`player_id` = 3 then `h`.`playing_hcp` end) AS `p3_hcp`,
    max(case when `h`.`player_id` = 3 then `h`.`net_score` end) AS `p3_net`,
    max(case when `h`.`player_id` = 4 then `h`.`player_name` end) AS `p4_name`,
    max(case when `h`.`player_id` = 4 then `p`.`winner_colour` end) AS `p4_colour`,
    max(case when `h`.`player_id` = 4 then `h`.`gross_score` end) AS `p4_gross`,
    max(case when `h`.`player_id` = 4 then `h`.`playing_hcp` end) AS `p4_hcp`,
    max(case when `h`.`player_id` = 4 then `h`.`net_score` end) AS `p4_net`
from
    ((`view_golf_rounds` `r`
left join `wp_golf_dashboard_history` `h` on
    (`h`.`date_played` = `r`.`date_played` and `h`.`tee_colour` = `r`.`tee_colour`))
left join `wp_golf_players` `p` on
    (`p`.`player_id` = `h`.`player_id`))
group by
    `r`.`date_played`,
    `r`.`tee_colour`,
    `r`.`player_count`,
    `r`.`winners_count`,
    `r`.`winner_player`,
    `r`.`winner_colour`;
-- END_QUERY