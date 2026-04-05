DROP VIEW IF EXISTS `view_handicap_index`;
-- END_QUERY

-- WATERMARK 1.0.68
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_handicap_index` AS
select
    `p`.`player_id` AS `player_id`,
    `p`.`name` AS `player_name`,
    coalesce(`h`.`rounds_in_window`, 0) AS `rounds_counted`,
    `h`.`hcp_after` AS `current_handicap_index`,
    `h`.`previous_hcp_after` AS `previous_handicap_index`,
    `h`.`low_hi_365` AS `low_hi_365`,
    case
        when `h`.`previous_hcp_after` is null then 'same'
        when `h`.`hcp_after` > `h`.`previous_hcp_after` then 'up'
        when `h`.`hcp_after` < `h`.`previous_hcp_after` then 'down'
        else 'same'
    end AS `hi_direction`
from
    (`wp_golf_players` `p`
left join (
    select
        `last`.`player_id` AS `player_id`,
        `last`.`hcp_after` AS `hcp_after`,
        `last`.`low_hi_365` AS `low_hi_365`,
        (
        select
            `prev`.`hcp_after`
        from
            `wp_golf_handicap_history` `prev`
        where
            `prev`.`player_id` = `last`.`player_id`
            and (
                `prev`.`date_played` < `last`.`date_played`
                or (
                    `prev`.`date_played` = `last`.`date_played`
                    and `prev`.`score_id` < `last`.`score_id`
                )
            )
        order by
            `prev`.`date_played` desc,
            `prev`.`score_id` desc
        limit 1) AS `previous_hcp_after`,
        (
        select
            least(count(0), 20)
        from
            `wp_golf_handicap_history` `h2`
        where
            `h2`.`player_id` = `last`.`player_id`
            and (
                `h2`.`date_played` < `last`.`date_played`
                or (
                    `h2`.`date_played` = `last`.`date_played`
                    and `h2`.`score_id` <= `last`.`score_id`
                )
            )
        ) AS `rounds_in_window`
    from
        ((`wp_golf_handicap_history` `last`
    join (
        select
            `hh`.`player_id` AS `player_id`,
            max(`hh`.`date_played`) AS `max_date`
        from
            `wp_golf_handicap_history` `hh`
        group by
            `hh`.`player_id`) `mx` on
        (`mx`.`player_id` = `last`.`player_id` and `mx`.`max_date` = `last`.`date_played`))
    join (
        select
            `hh`.`player_id` AS `player_id`,
            `hh`.`date_played` AS `date_played`,
            max(`hh`.`score_id`) AS `max_score_id`
        from
            `wp_golf_handicap_history` `hh`
        group by
            `hh`.`player_id`,
            `hh`.`date_played`) `ms` on
        (`ms`.`player_id` = `last`.`player_id`
         and `ms`.`date_played` = `last`.`date_played`
         and `ms`.`max_score_id` = `last`.`score_id`)) `h` on
    (`h`.`player_id` = `p`.`player_id`));
-- END_QUERY