CREATE OR REPLACE VIEW view_eclectic_players AS
SELECT player_id, name
FROM wp_golf_players
WHERE name IN ('Phil D', 'Phil B', 'Jay', 'Adder')
ORDER BY FIELD(name, 'Phil D', 'Phil B', 'Jay', 'Adder');