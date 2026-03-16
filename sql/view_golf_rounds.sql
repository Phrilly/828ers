DROP VIEW IF EXISTS `view_golf_rounds`;
-- END_QUERY

-- WATERMARK 1.0.33
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_rounds` AS
select
    `e`.`date_played` AS `date_played`,
    `e`.`tee_colour` AS `tee_colour`,
    max(`e`.`player_count`) AS `player_count`,
    min(`e`.`net_score`) AS `best_nett_score`,
    sum(case when `e`.`nett_position` = 1 then 1 else 0 end) AS `winners_count`,
    case
        when sum(case when `e`.`nett_position` = 1 then 1 else 0 end) = 1 then max(case when `e`.`nett_position` = 1 then `e`.`player` end)
        else NULL
    end AS `winner_player`,
    case
        when sum(case when `e`.`nett_position` = 1 then 1 else 0 end) = 1 then max(case when `e`.`nett_position` = 1 then `p`.`winner_colour` end)
        else NULL
    end AS `winner_colour`
from
    (`view_golf_round_entries` `e`
left join `wp_golf_players` `p` on
    (`p`.`name` = `e`.`player`))
group by
    `e`.`date_played`,
    `e`.`tee_colour`;
-- END_QUERY