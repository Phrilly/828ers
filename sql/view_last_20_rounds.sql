DROP VIEW IF EXISTS `view_last_20_rounds`;
-- END_QUERY

-- WATERMARK 1.0.95
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_last_20_rounds` AS
select
    `view_round_differentials`.`player_id` AS `player_id`,
    `view_round_differentials`.`score_id` AS `score_id`,
    `view_round_differentials`.`differential` AS `differential`
from
    `view_round_differentials`
where
    `view_round_differentials`.`recency_rank` <= 20;
-- END_QUERY