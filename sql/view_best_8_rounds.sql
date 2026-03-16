-- view_best_8_rounds
DROP VIEW IF EXISTS `view_best_8_rounds`;

CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_best_8_rounds` AS
select
    `v20`.`player_id` AS `player_id`,
    `v20`.`score_id` AS `score_id`,
    `v20`.`differential` AS `differential`
from
    `view_last_20_rounds` `v20`
where
    (
    select
        count(0)
    from
        `view_last_20_rounds` `vComp`
    where
        `vComp`.`player_id` = `v20`.`player_id`
        and (`vComp`.`differential` < `v20`.`differential`
            or `vComp`.`differential` = `v20`.`differential`
            and `vComp`.`score_id` <= `v20`.`score_id`)) <= 8;

-- END_QUERY
