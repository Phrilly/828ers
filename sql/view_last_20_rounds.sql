CREATE OR REPLACE VIEW `view_last_20_rounds` AS
SELECT
    h.player_id      AS player_id,
    h.score_id       AS score_id,
    h.date_played    AS date_played,
    h.differential   AS differential   -- ESR-adjusted value
FROM wp_golf_handicap_history h
WHERE h.score_id IN (
    SELECT score_id
    FROM wp_golf_handicap_history
    WHERE player_id = h.player_id
    ORDER BY date_played DESC, score_id DESC
    LIMIT 20
);