DROP VIEW IF EXISTS `view_golf_yearly_stats`;
-- END_QUERY

-- WATERMARK 1.0.44
CREATE OR REPLACE ALGORITHM = UNDEFINED VIEW `view_golf_yearly_stats` AS
select
    `p`.`name` AS `player_name`,
    year(`s`.`date_played`) AS `stat_year`,
    count(`s`.`score_id`) AS `total_rounds`,
    round(avg(`s`.`gross_score`), 1) AS `avg_gross_year`,

    /* Logic: If putts is 0, treat as NULL so it's ignored by the AVG function */
    ROUND(AVG(CASE WHEN s.putts > 0 THEN s.putts ELSE NULL END), 1) AS avg_putts_year, 
    ROUND(AVG(CASE WHEN s.putts > 0 THEN s.gir ELSE NULL END), 1) AS avg_gir_year,
    
    sum(case when `s`.`gross_score` < 80 then 1 else 0 end) AS `sub_80`,
    sum(case when `s`.`gross_score` between 80 and 84 then 1 else 0 end) AS `cat_80_84`,
    sum(case when `s`.`gross_score` between 85 and 89 then 1 else 0 end) AS `cat_85_89`,
    sum(case when `s`.`gross_score` between 90 and 99 then 1 else 0 end) AS `cat_90_99`,
    sum(case when `s`.`gross_score` >= 100 then 1 else 0 end) AS `cat_100_plus`,
    sum(case when `e`.`is_win_nett` = 1 and `e`.`player_count` > 1 then 1 else 0 end) AS `wins`,
    round((sum(case when `e`.`is_win_nett` = 1 and `e`.`player_count` > 1 then 1 else 0 end) / count(`s`.`score_id`)) * 100, 1) AS `win_pct`
from
    ((`wp_golf_scores` `s`
join `wp_golf_players` `p` on
    (`p`.`player_id` = `s`.`player_id`))
left join `view_golf_round_entries` `e` on
    (`e`.`score_id` = `s`.`score_id`))
where
    `s`.`is_excluded` = 0
group by
    `p`.`name`,
    year(`s`.`date_played`);
-- END_QUERY