-- phpMyAdmin SQL Dump
-- version 5.2.2
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1:3306
-- Generation Time: Mar 15, 2026 at 11:15 AM
-- Server version: 11.8.3-MariaDB-log
-- PHP Version: 7.2.34

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `u271511030_9syka`
--

DELIMITER $$
--
-- Procedures
--
DROP PROCEDURE IF EXISTS `sp_build_view_golf_rounds_pivot`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_build_view_golf_rounds_pivot` ()   BEGIN
  DECLARE vCols LONGTEXT;

  -- Build pivot columns for all players, using dashboard_history (has playing_hcp)
  SELECT GROUP_CONCAT(
    CONCAT(
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.player_name END) AS `p', p.player_id, '_name`, ',
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.gross_score END) AS `p', p.player_id, '_gross`, ',
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.playing_hcp END) AS `p', p.player_id, '_hcp`, ',
      'MAX(CASE WHEN h.player_id = ', p.player_id, ' THEN h.net_score END) AS `p', p.player_id, '_net`'
    )
    ORDER BY p.player_id SEPARATOR ', '
  )
  INTO vCols
  FROM wp_golf_players p;

  SET @sql = CONCAT(
    'CREATE OR REPLACE VIEW view_golf_rounds_pivot AS
     SELECT
       r.date_played,
       MAX(h.tee_id) AS tee_id,
       r.tee_colour,
       CASE WHEN r.winners_count > 1 THEN ''TIE'' ELSE r.winner_player END AS winner,
       '''' AS winner_colour,
       ', vCols, '
     FROM view_golf_rounds r
     LEFT JOIN wp_golf_dashboard_history h
       ON h.date_played = r.date_played
      AND h.tee_colour  = r.tee_colour
     GROUP BY r.date_played, r.tee_colour'
  );

  PREPARE stmt FROM @sql;
  EXECUTE stmt;
  DEALLOCATE PREPARE stmt;
END$$

DROP PROCEDURE IF EXISTS `sp_get_whs_index_at_point`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_get_whs_index_at_point` (IN `p_player_id` INT, IN `p_date` DATE, IN `p_score_id` INT, OUT `p_calculated_index` DECIMAL(5,1))   BEGIN
    -- We use a triple-nested query to ensure the LIMIT 8 applies 
    -- to the sorted list of differentials, not the average.
    SELECT ROUND(AVG(best_8.diff), 1) INTO p_calculated_index
    FROM (
        SELECT last_20.diff
        FROM (
            -- 1. Get the last 20 scores BEFORE the current round
            SELECT differential AS diff
            FROM wp_golf_handicap_history
            WHERE player_id = p_player_id
              AND (date_played < p_date OR (date_played = p_date AND score_id < p_score_id))
            ORDER BY date_played DESC, score_id DESC
            LIMIT 20
        ) AS last_20
        -- 2. Sort those 20 from best (lowest) to worst
        ORDER BY last_20.diff ASC
        -- 3. Take only the best 8
        LIMIT 8
    ) AS best_8;

    -- Default for new players
    IF p_calculated_index IS NULL THEN SET p_calculated_index = 54.0; END IF;
END$$

DROP PROCEDURE IF EXISTS `sp_process_single_round`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_process_single_round` (IN `p_score_id` INT)   sp_label: BEGIN
    DECLARE v_player_id     INT;
    DECLARE v_date_played   DATE;
    DECLARE v_gross_score   INT;
    DECLARE v_pcc           DECIMAL(4,1);
    DECLARE v_course_rating DECIMAL(4,1);
    DECLARE v_slope_rating  INT;
    DECLARE v_par           INT;
    DECLARE v_diff_raw      DECIMAL(5,1);
    DECLARE v_hcp_before    DECIMAL(5,1);
    DECLARE v_hcp_unadj     DECIMAL(5,3);
    DECLARE v_hcp_working   DECIMAL(5,3);
    DECLARE v_low_hi_365    DECIMAL(5,3);
    DECLARE v_esr_amount    DECIMAL(5,2) DEFAULT 0.00;
    DECLARE v_cap_type      VARCHAR(10)  DEFAULT 'NONE';
    DECLARE v_cap_reduction DECIMAL(5,3) DEFAULT 0.000;
    DECLARE v_cap_original  DECIMAL(5,3);
    DECLARE v_course_hcp    DECIMAL(5,2);
    DECLARE v_playing_hcp   INT;
    DECLARE v_net_score     INT;

    SELECT s.player_id, s.date_played, s.gross_score,
           COALESCE(s.pcc_adjustment, 0),
           t.course_rating, t.slope_rating, t.par
    INTO   v_player_id, v_date_played, v_gross_score, v_pcc,
           v_course_rating, v_slope_rating, v_par
    FROM   wp_golf_scores s
    JOIN   wp_golf_tees   t ON s.tee_id = t.tee_id
    WHERE  s.score_id = p_score_id;

    IF (SELECT is_excluded FROM wp_golf_scores WHERE score_id = p_score_id) = 1 THEN
        DELETE FROM wp_golf_handicap_history WHERE score_id = p_score_id;
        LEAVE sp_label;
    END IF;

    SET v_diff_raw = ROUND(113.0 / v_slope_rating * (v_gross_score - v_course_rating - v_pcc), 1);

    INSERT INTO wp_golf_handicap_history
        (player_id, score_id, date_played, diff_raw, differential, esr_adj, esr_triggered, esr_amount, cap_type, cap_reduction)
    VALUES
        (v_player_id, p_score_id, v_date_played, v_diff_raw, v_diff_raw, 0.0, 0, 0.0, 'NONE', 0.000)
    ON DUPLICATE KEY UPDATE
        diff_raw      = v_diff_raw,
        differential  = v_diff_raw,
        esr_adj       = 0.0,
        esr_triggered = 0,
        esr_amount    = 0.0,
        cap_type      = 'NONE',
        cap_reduction = 0.000;

    SELECT COALESCE(
        (SELECT hcp_after FROM wp_golf_handicap_history
         WHERE  player_id = v_player_id
         AND    (date_played < v_date_played OR (date_played = v_date_played AND score_id < p_score_id))
         ORDER BY date_played DESC, score_id DESC LIMIT 1),
        54.0
    ) INTO v_hcp_before;
    UPDATE wp_golf_handicap_history SET hcp_before = v_hcp_before WHERE score_id = p_score_id;

    SELECT ROUND(AVG(d), 3) INTO v_hcp_unadj
    FROM (
        SELECT differential AS d
        FROM (
            SELECT differential FROM wp_golf_handicap_history
            WHERE player_id = v_player_id
            AND (date_played < v_date_played OR (date_played = v_date_played AND score_id <= p_score_id))
            ORDER BY date_played DESC, score_id DESC LIMIT 20
        ) AS last20
        ORDER BY differential ASC LIMIT 8
    ) AS best8;
    UPDATE wp_golf_handicap_history SET hcp_unadjusted = v_hcp_unadj WHERE score_id = p_score_id;
    SET v_hcp_working = v_hcp_unadj;

    IF v_diff_raw < v_hcp_before - 7.0 THEN
        IF v_diff_raw < v_hcp_before - 10.0 THEN
            SET v_esr_amount = -2.00;
        ELSE
            SET v_esr_amount = -1.00;
        END IF;

        UPDATE wp_golf_handicap_history h
        INNER JOIN (
            SELECT score_id FROM wp_golf_handicap_history
            WHERE player_id = v_player_id
            AND (date_played < v_date_played OR (date_played = v_date_played AND score_id <= p_score_id))
            ORDER BY date_played DESC, score_id DESC LIMIT 20
        ) AS last20 ON h.score_id = last20.score_id
        SET h.esr_adj = h.esr_adj + v_esr_amount;

        UPDATE wp_golf_handicap_history h
        INNER JOIN (
            SELECT score_id FROM wp_golf_handicap_history
            WHERE player_id = v_player_id
            AND (date_played < v_date_played OR (date_played = v_date_played AND score_id <= p_score_id))
            ORDER BY date_played DESC, score_id DESC LIMIT 20
        ) AS last20 ON h.score_id = last20.score_id
        SET h.differential = h.diff_raw + h.esr_adj;

        UPDATE wp_golf_handicap_history
        SET esr_triggered = 1, esr_amount = v_esr_amount
        WHERE score_id = p_score_id;

        SELECT ROUND(AVG(d), 3) INTO v_hcp_working
        FROM (
            SELECT differential AS d
            FROM (
                SELECT differential FROM wp_golf_handicap_history
                WHERE player_id = v_player_id
                AND (date_played < v_date_played OR (date_played = v_date_played AND score_id <= p_score_id))
                ORDER BY date_played DESC, score_id DESC LIMIT 20
            ) AS last20
            ORDER BY differential ASC LIMIT 8
        ) AS best8;
    END IF;

    SELECT COALESCE(MIN(hcp_after), v_hcp_working) INTO v_low_hi_365
    FROM wp_golf_handicap_history
    WHERE player_id   = v_player_id
    AND   date_played >= DATE_SUB(v_date_played, INTERVAL 365 DAY)
    AND   date_played <  v_date_played
    AND   score_id    != p_score_id
    AND   hcp_after IS NOT NULL;

    SET v_cap_original = v_hcp_working;
    IF v_hcp_working > v_low_hi_365 + 3.0 THEN
        SET v_cap_type    = 'SOFT';
        SET v_hcp_working = v_low_hi_365 + 3.0 + (v_hcp_working - (v_low_hi_365 + 3.0)) * 0.5;
        IF v_hcp_working > v_low_hi_365 + 5.0 THEN
            SET v_cap_type    = 'HARD';
            SET v_hcp_working = v_low_hi_365 + 5.0;
        END IF;
        SET v_cap_reduction = v_cap_original - v_hcp_working;
    END IF;

    SET v_hcp_working = ROUND(v_hcp_working, 1);
    UPDATE wp_golf_handicap_history
    SET hcp_after = v_hcp_working, cap_type = v_cap_type, cap_reduction = v_cap_reduction
    WHERE score_id = p_score_id;

    SELECT COALESCE(MIN(hcp_after), v_hcp_working) INTO v_low_hi_365
    FROM wp_golf_handicap_history
    WHERE player_id   = v_player_id
    AND   date_played >= DATE_SUB(v_date_played, INTERVAL 1 YEAR)
    AND   date_played <= v_date_played
    AND   hcp_after IS NOT NULL;
    UPDATE wp_golf_handicap_history SET low_hi_365 = v_low_hi_365 WHERE score_id = p_score_id;

    SET v_course_hcp  = ROUND(v_hcp_before * v_slope_rating / 113.0 + (v_course_rating - v_par), 2);
    SET v_playing_hcp = ROUND(v_course_hcp * 0.95, 0);
    SET v_net_score   = v_gross_score - v_playing_hcp;
    UPDATE wp_golf_handicap_history
    SET course_hcp = v_course_hcp, playing_hcp = v_playing_hcp, net_score = v_net_score
    WHERE score_id = p_score_id;

END$$

DROP PROCEDURE IF EXISTS `sp_rebuild_all_players`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_rebuild_all_players` ()   BEGIN
    DECLARE v_player_id  INT;
    DECLARE v_first_date DATE;
    DECLARE v_done       TINYINT DEFAULT 0;

    DECLARE cur CURSOR FOR
        SELECT player_id, MIN(date_played)
        FROM   wp_golf_scores
        WHERE  is_excluded = 0
        GROUP BY player_id;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    TRUNCATE TABLE wp_golf_handicap_history;

    OPEN cur;
    playerloop: LOOP
        FETCH cur INTO v_player_id, v_first_date;
        IF v_done THEN LEAVE playerloop; END IF;
        CALL sp_repair_from_date(v_player_id, v_first_date);
    END LOOP;
    CLOSE cur;

    CALL sp_build_view_golf_rounds_pivot();
END$$

DROP PROCEDURE IF EXISTS `sp_refresh_best8_flags`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_refresh_best8_flags` (IN `p_player_id` INT)   BEGIN
    UPDATE wp_golf_handicap_history SET is_best_8 = 0 WHERE player_id = p_player_id;

    UPDATE wp_golf_handicap_history h
    INNER JOIN (
        SELECT score_id FROM (
            SELECT score_id, differential
            FROM wp_golf_handicap_history
            WHERE player_id = p_player_id
            ORDER BY date_played DESC, score_id DESC
            LIMIT 20
        ) AS last20
        ORDER BY differential ASC
        LIMIT 8
    ) AS best8 ON h.score_id = best8.score_id
    SET h.is_best_8 = 1;
END$$

DROP PROCEDURE IF EXISTS `sp_refresh_best_8_flags`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_refresh_best_8_flags` (IN `p_player_id` INT)   BEGIN
    -- 1. Clear all existing flags for this player
    UPDATE wp_golf_handicap_history
    SET is_best_8 = 0
    WHERE player_id = p_player_id;

    -- 2. Identify and set is_best_8 = 1 for the best 8 of the last 20 rounds
    UPDATE wp_golf_handicap_history h
    INNER JOIN (
        SELECT score_id
        FROM (
            SELECT score_id, differential
            FROM wp_golf_handicap_history
            WHERE player_id = p_player_id
            ORDER BY date_played DESC, score_id DESC
            LIMIT 20
        ) AS last_20
        ORDER BY differential ASC
        LIMIT 8
    ) AS best_8 ON h.score_id = best_8.score_id
    SET h.is_best_8 = 1;
END$$

DROP PROCEDURE IF EXISTS `sp_repair_entire_history`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_repair_entire_history` (IN `p_player_id` INT)   BEGIN
    DECLARE done        INT DEFAULT 0;
    DECLARE v_score_id  INT;
    DECLARE v_tee_id    INT;
    DECLARE v_gross     INT;
    DECLARE v_slope     INT;
    DECLARE v_par       INT;
    DECLARE v_date      DATE;
    DECLARE v_pcc       DECIMAL(5,1);
    DECLARE v_rating    DECIMAL(5,1);
    DECLARE v_diff      DECIMAL(5,1);
    DECLARE v_idx_start DECIMAL(5,1);

    DECLARE cur CURSOR FOR
        SELECT s.score_id, s.date_played, s.tee_id, s.gross_score,
               COALESCE(s.pcc_adjustment, 0),
               t.slope_rating, t.course_rating, t.par
        FROM   wp_golf_scores s
        JOIN   wp_golf_tees   t ON s.tee_id = t.tee_id
        WHERE  s.player_id   = p_player_id
        AND    s.is_excluded  = 0
        ORDER BY s.date_played ASC, s.score_id ASC;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    DELETE FROM wp_golf_handicap_history WHERE player_id = p_player_id;

    OPEN cur;
    readloop: LOOP
        FETCH cur INTO v_score_id, v_date, v_tee_id, v_gross, v_pcc, v_slope, v_rating, v_par;
        IF done THEN LEAVE readloop; END IF;
        CALL sp_get_whs_index_at_point(p_player_id, v_date, v_score_id, v_idx_start);
        SET v_diff = ROUND(113.0 / v_slope * (v_gross - v_rating - v_pcc), 1);
        INSERT INTO wp_golf_handicap_history (player_id, score_id, date_played, hcp_before, playing_hcp, differential)
        VALUES (p_player_id, v_score_id, v_date, v_idx_start,
                ROUND(v_idx_start * v_slope / 113.0 + (v_rating - v_par), 0), v_diff);
    END LOOP;
    CLOSE cur;

    CALL sp_refresh_best8_flags(p_player_id);
END$$

DROP PROCEDURE IF EXISTS `sp_repair_from_date`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_repair_from_date` (IN `p_player_id` INT, IN `p_start_date` DATE)   BEGIN
    DECLARE v_score_id INT;
    DECLARE v_done TINYINT DEFAULT 0;

    DECLARE cur CURSOR FOR
        SELECT score_id FROM wp_golf_scores
        WHERE  player_id   = p_player_id
        AND    date_played >= p_start_date
        AND    is_excluded  = 0
        ORDER BY date_played ASC, score_id ASC;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    UPDATE wp_golf_handicap_history
    SET    esr_adj = 0.0, differential = diff_raw, esr_triggered = 0, esr_amount = 0.0
    WHERE  player_id   = p_player_id
    AND    date_played >= p_start_date;

    DELETE h FROM wp_golf_handicap_history h
    LEFT JOIN wp_golf_scores s ON s.score_id = h.score_id
    WHERE h.player_id   = p_player_id
    AND   h.date_played >= p_start_date
    AND   (s.score_id IS NULL OR s.is_excluded = 1);

    OPEN cur;
    readloop: LOOP
        FETCH cur INTO v_score_id;
        IF v_done THEN LEAVE readloop; END IF;
        CALL sp_process_single_round(v_score_id);
    END LOOP;
    CLOSE cur;

    CALL sp_refresh_best8_flags(p_player_id);
END$$

DROP PROCEDURE IF EXISTS `sp_repair_handicap_history`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_repair_handicap_history` (IN `p_id` INT)   BEGIN
    

    DELETE FROM wp_golf_handicap_history
    WHERE player_id = p_id;

    INSERT INTO wp_golf_handicap_history (player_id, score_id, date_played, hcp_before)
    SELECT
        s1.player_id,
        s1.score_id,
        s1.date_played,
        (
            
            SELECT ROUND(
                AVG(
                    (113 / t2.Slope_Rating) *
                    (s2.gross_score - t2.Course_Rating - COALESCE(s2.pcc_adjustment, 0))
                ),
                1
            )
            FROM wp_golf_scores s2
            JOIN wp_golf_tees t2 ON s2.tee_id = t2.tee_id
            WHERE s2.player_id = p_id
              AND (
                    s2.date_played < s1.date_played
                 OR (s2.date_played = s1.date_played AND s2.score_id < s1.score_id)
              )
            ORDER BY s2.date_played DESC, s2.score_id DESC
            LIMIT 20
        ) AS hcp_before
    FROM wp_golf_scores s1
    WHERE s1.player_id = p_id
    ORDER BY s1.date_played ASC, s1.score_id ASC;
END$$

DROP PROCEDURE IF EXISTS `sp_update_low_hi_365`$$
CREATE DEFINER=`u271511030_AFpgR`@`127.0.0.1` PROCEDURE `sp_update_low_hi_365` (IN `p_score_id` INT)   BEGIN
  DECLARE v_player_id INT;
  DECLARE v_date_played DATE;
  DECLARE v_low_hi DECIMAL(5,2);

  SELECT s.player_id, s.date_played
    INTO v_player_id, v_date_played
  FROM wp_golf_scores s
  WHERE s.score_id = p_score_id;

  SELECT MIN(h.hcp_after)
    INTO v_low_hi
  FROM wp_golf_handicap_history h
  WHERE h.player_id = v_player_id
    AND h.date_played >= DATE_SUB(v_date_played, INTERVAL 1 YEAR)
    AND (
         h.date_played < v_date_played
      OR (h.date_played = v_date_played AND h.score_id < p_score_id)
    );

  UPDATE wp_golf_handicap_history
  SET low_hi_365 = v_low_hi
  WHERE score_id = p_score_id;
END$$

DELIMITER ;

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_best_8_rounds`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_best_8_rounds`;
CREATE TABLE `view_best_8_rounds` (
`player_id` int(11)
,`score_id` int(11)
,`differential` decimal(17,1)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_daily_winners`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_daily_winners`;
CREATE TABLE `view_golf_daily_winners` (
`date_played` date
,`tee_colour` varchar(50)
,`winner_id` int(11)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_dashboard_history`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_dashboard_history`;
CREATE TABLE `view_golf_dashboard_history` (
`score_id` int(11)
,`player_name` varchar(50)
,`date_played` date
,`tee_colour` varchar(50)
,`gross_score` int(11)
,`starting_index` decimal(5,1)
,`playing_hcp` int(11)
,`net_score` int(11)
,`differential` decimal(5,1)
,`is_counting` tinyint(1)
,`cap_applied` int(1)
,`esr_applied` int(1)
,`cap_type` enum('NONE','SOFT','HARD')
,`cap_reduction` decimal(5,3)
,`esr_triggered` tinyint(1)
,`esr_amount` decimal(5,3)
,`esr_adj` decimal(3,1)
,`adj_flag` varchar(8)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_players_pivot_names`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_players_pivot_names`;
CREATE TABLE `view_golf_players_pivot_names` (
`p1_name` varchar(50)
,`p2_name` varchar(50)
,`p3_name` varchar(50)
,`p4_name` varchar(50)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_player_records`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_player_records`;
CREATE TABLE `view_golf_player_records` (
`player_id` int(11)
,`player_name` varchar(50)
,`best_score` int(11)
,`best_date` date
,`streak_count` bigint(21)
,`streak_start` date
,`streak_end` date
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_rolling_averages`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_rolling_averages`;
CREATE TABLE `view_golf_rolling_averages` (
`player_id` int(11)
,`player_name` varchar(50)
,`avg_putts_20` decimal(12,1)
,`avg_gir_20` decimal(12,1)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_rounds`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_rounds`;
CREATE TABLE `view_golf_rounds` (
`date_played` date
,`tee_colour` varchar(50)
,`player_count` bigint(21)
,`best_nett_score` int(11)
,`winners_count` decimal(22,0)
,`winner_player` varchar(50)
,`winner_colour` varchar(20)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_rounds_pivot`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_rounds_pivot`;
CREATE TABLE `view_golf_rounds_pivot` (
`date_played` date
,`tee_colour` varchar(50)
,`winner` varchar(50)
,`winner_colour` varchar(20)
,`p1_name` varchar(50)
,`p1_colour` varchar(20)
,`p1_gross` bigint(11)
,`p1_hcp` bigint(11)
,`p1_net` bigint(11)
,`p2_name` varchar(50)
,`p2_colour` varchar(20)
,`p2_gross` bigint(11)
,`p2_hcp` bigint(11)
,`p2_net` bigint(11)
,`p3_name` varchar(50)
,`p3_colour` varchar(20)
,`p3_gross` bigint(11)
,`p3_hcp` bigint(11)
,`p3_net` bigint(11)
,`p4_name` varchar(50)
,`p4_colour` varchar(20)
,`p4_gross` bigint(11)
,`p4_hcp` bigint(11)
,`p4_net` bigint(11)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_round_entries`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_round_entries`;
CREATE TABLE `view_golf_round_entries` (
`date_played` date
,`tee_colour` varchar(50)
,`player` varchar(50)
,`score_id` int(11)
,`gross_score` int(11)
,`net_score` int(11)
,`hcp_index_start` decimal(5,1)
,`nett_position` bigint(21)
,`player_count` bigint(21)
,`is_draw_nett` int(1)
,`is_win_nett` int(1)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_win_streaks`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_win_streaks`;
CREATE TABLE `view_golf_win_streaks` (
`player` varchar(50)
,`streak_start_date` date
,`streak_start_tee` varchar(50)
,`streak_end_date` date
,`streak_end_tee` varchar(50)
,`streak_wins` bigint(21)
,`first_score_id` int(11)
,`last_score_id` int(11)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_golf_yearly_stats`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_golf_yearly_stats`;
CREATE TABLE `view_golf_yearly_stats` (
`player_name` varchar(50)
,`stat_year` int(5)
,`total_rounds` bigint(21)
,`avg_gross_year` decimal(12,1)
,`avg_putts_year` decimal(12,1)
,`avg_gir_year` decimal(12,1)
,`sub_80` decimal(22,0)
,`cat_80_84` decimal(22,0)
,`cat_85_89` decimal(22,0)
,`cat_90_99` decimal(22,0)
,`cat_100_plus` decimal(22,0)
,`wins` decimal(22,0)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_handicap_index`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_handicap_index`;
CREATE TABLE `view_handicap_index` (
`player_id` int(11)
,`player_name` varchar(50)
,`rounds_counted` bigint(21)
,`current_handicap_index` decimal(5,1)
,`previous_handicap_index` decimal(5,1)
,`hi_direction` varchar(4)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_last_20_rounds`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_last_20_rounds`;
CREATE TABLE `view_last_20_rounds` (
`player_id` int(11)
,`score_id` int(11)
,`differential` decimal(17,1)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_playing_handicaps`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_playing_handicaps`;
CREATE TABLE `view_playing_handicaps` (
`player_id` int(11)
,`player_name` varchar(50)
,`white_exact` decimal(18,2)
,`white_play` decimal(17,0)
,`yellow_exact` decimal(18,2)
,`yellow_play` decimal(17,0)
,`black_exact` decimal(18,2)
,`black_play` decimal(17,0)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_round_differentials`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_round_differentials`;
CREATE TABLE `view_round_differentials` (
`player_id` int(11)
,`score_id` int(11)
,`date_played` date
,`gross_score` int(11)
,`differential` decimal(17,1)
,`recency_rank` bigint(22)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_scoreboard`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `view_scoreboard`;
CREATE TABLE `view_scoreboard` (
`score_id` int(11)
,`player` varchar(50)
,`course_name` varchar(100)
,`tee_colour` varchar(50)
,`date_played` date
,`gross_score` int(11)
,`current_index` decimal(5,1)
,`playing_handicap` int(11)
,`net_score` int(11)
,`putts` int(11)
,`gir` int(11)
,`pcc_adjustment` int(11)
,`handicap_differential` decimal(5,1)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `wp_golf_dashboard_history`
-- (See below for the actual view)
--
DROP VIEW IF EXISTS `wp_golf_dashboard_history`;
CREATE TABLE `wp_golf_dashboard_history` (
`score_id` int(11)
,`date_played` date
,`player_id` int(11)
,`player_name` varchar(50)
,`tee_id` int(11)
,`tee_colour` varchar(50)
,`gross_score` int(11)
,`pcc_adjustment` int(11)
,`index` decimal(5,1)
,`starting_index` decimal(5,1)
,`playing_hcp` int(11)
,`net_score` int(11)
,`differential` decimal(5,1)
,`putts` int(11)
,`gir` int(11)
,`is_counting` tinyint(1)
,`cap_applied` int(1)
,`esr_applied` int(1)
,`cap_type` enum('NONE','SOFT','HARD')
,`cap_reduction` decimal(5,3)
,`esr_triggered` tinyint(1)
,`esr_amount` decimal(5,3)
,`is_excluded` tinyint(1)
);

-- --------------------------------------------------------

--
-- Structure for view `view_best_8_rounds`
--
DROP TABLE IF EXISTS `view_best_8_rounds`;

DROP VIEW IF EXISTS `view_best_8_rounds`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_best_8_rounds`  AS SELECT `v20`.`player_id` AS `player_id`, `v20`.`score_id` AS `score_id`, `v20`.`differential` AS `differential` FROM `view_last_20_rounds` AS `v20` WHERE (select count(0) from `view_last_20_rounds` `vComp` where `vComp`.`player_id` = `v20`.`player_id` AND (`vComp`.`differential` < `v20`.`differential` OR `vComp`.`differential` = `v20`.`differential` AND `vComp`.`score_id` <= `v20`.`score_id`)) <= 8 ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_daily_winners`
--
DROP TABLE IF EXISTS `view_golf_daily_winners`;

DROP VIEW IF EXISTS `view_golf_daily_winners`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_daily_winners`  AS WITH DailyRanks AS (SELECT `wp_golf_dashboard_history`.`date_played` AS `date_played`, `wp_golf_dashboard_history`.`tee_colour` AS `tee_colour`, `wp_golf_dashboard_history`.`player_id` AS `player_id`, `wp_golf_dashboard_history`.`net_score` AS `net_score`, min(`wp_golf_dashboard_history`.`net_score`) over ( partition by `wp_golf_dashboard_history`.`date_played`,`wp_golf_dashboard_history`.`tee_colour`) AS `best_score`, count(0) over ( partition by `wp_golf_dashboard_history`.`date_played`,`wp_golf_dashboard_history`.`tee_colour`) AS `field_size` FROM `wp_golf_dashboard_history`) SELECT `DailyRanks`.`date_played` AS `date_played`, `DailyRanks`.`tee_colour` AS `tee_colour`, `DailyRanks`.`player_id` AS `winner_id` FROM `DailyRanks` WHERE `DailyRanks`.`net_score` = `DailyRanks`.`best_score` AND `DailyRanks`.`field_size` > 1 AND (select count(0) from `wp_golf_dashboard_history` `h2` where `h2`.`date_played` = `DailyRanks`.`date_played` AND `h2`.`tee_colour` = `DailyRanks`.`tee_colour` AND `h2`.`net_score` = `DailyRanks`.`best_score`) = 11  ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_dashboard_history`
--
DROP TABLE IF EXISTS `view_golf_dashboard_history`;

DROP VIEW IF EXISTS `view_golf_dashboard_history`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_dashboard_history`  AS SELECT `s`.`score_id` AS `score_id`, `p`.`name` AS `player_name`, `s`.`date_played` AS `date_played`, `t`.`tee_colour` AS `tee_colour`, `s`.`gross_score` AS `gross_score`, `h`.`hcp_before` AS `starting_index`, `h`.`playing_hcp` AS `playing_hcp`, `h`.`net_score` AS `net_score`, `h`.`differential` AS `differential`, `h`.`is_best_8` AS `is_counting`, CASE WHEN `h`.`cap_type` is not null AND `h`.`cap_type` <> 'NONE' THEN 1 ELSE 0 END AS `cap_applied`, CASE WHEN `h`.`esr_triggered` = 1 THEN 1 ELSE 0 END AS `esr_applied`, `h`.`cap_type` AS `cap_type`, `h`.`cap_reduction` AS `cap_reduction`, `h`.`esr_triggered` AS `esr_triggered`, `h`.`esr_amount` AS `esr_amount`, `h`.`esr_adj` AS `esr_adj`, trim(concat(case when `h`.`esr_triggered` = 1 then 'ESR ' else '' end,case when `h`.`cap_type` is not null and `h`.`cap_type` <> 'NONE' then `h`.`cap_type` else '' end)) AS `adj_flag` FROM (((`wp_golf_scores` `s` join `wp_golf_players` `p` on(`p`.`player_id` = `s`.`player_id`)) join `wp_golf_tees` `t` on(`t`.`tee_id` = `s`.`tee_id`)) left join `wp_golf_handicap_history` `h` on(`h`.`score_id` = `s`.`score_id`)) ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_players_pivot_names`
--
DROP TABLE IF EXISTS `view_golf_players_pivot_names`;

DROP VIEW IF EXISTS `view_golf_players_pivot_names`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_players_pivot_names`  AS SELECT max(case when `p`.`player_id` = 1 then `p`.`name` end) AS `p1_name`, max(case when `p`.`player_id` = 2 then `p`.`name` end) AS `p2_name`, max(case when `p`.`player_id` = 3 then `p`.`name` end) AS `p3_name`, max(case when `p`.`player_id` = 4 then `p`.`name` end) AS `p4_name` FROM `wp_golf_players` AS `p` ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_player_records`
--
DROP TABLE IF EXISTS `view_golf_player_records`;

DROP VIEW IF EXISTS `view_golf_player_records`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_player_records`  AS WITH rk1 AS (SELECT `v`.`score_id` AS `score_id`, `v`.`player` AS `player`, `v`.`course_name` AS `course_name`, `v`.`tee_colour` AS `tee_colour`, `v`.`date_played` AS `date_played`, `v`.`gross_score` AS `gross_score`, `v`.`current_index` AS `current_index`, `v`.`playing_handicap` AS `playing_handicap`, `v`.`net_score` AS `net_score`, `v`.`putts` AS `putts`, `v`.`gir` AS `gir`, `v`.`pcc_adjustment` AS `pcc_adjustment`, `v`.`handicap_differential` AS `handicap_differential`, rank() over ( partition by `v`.`date_played`,`v`.`tee_colour` order by `v`.`net_score`) AS `nett_rank` FROM `view_scoreboard` AS `v`), rk2 AS (SELECT `rk1`.`score_id` AS `score_id`, `rk1`.`player` AS `player`, `rk1`.`course_name` AS `course_name`, `rk1`.`tee_colour` AS `tee_colour`, `rk1`.`date_played` AS `date_played`, `rk1`.`gross_score` AS `gross_score`, `rk1`.`current_index` AS `current_index`, `rk1`.`playing_handicap` AS `playing_handicap`, `rk1`.`net_score` AS `net_score`, `rk1`.`putts` AS `putts`, `rk1`.`gir` AS `gir`, `rk1`.`pcc_adjustment` AS `pcc_adjustment`, `rk1`.`handicap_differential` AS `handicap_differential`, `rk1`.`nett_rank` AS `nett_rank`, sum(case when `rk1`.`nett_rank` = 1 then 1 else 0 end) over ( partition by `rk1`.`date_played`,`rk1`.`tee_colour`) AS `rank1_count` FROM `rk1`), WinSequence AS (SELECT `rk2`.`player` AS `player`, `rk2`.`date_played` AS `date_played`, `rk2`.`gross_score` AS `gross_score`, CASE WHEN `rk2`.`nett_rank` = 1 AND `rk2`.`rank1_count` = 1 THEN 1 ELSE 0 END AS `is_win`, `rk2`.`tee_colour` AS `tee_colour`, `rk2`.`score_id` AS `score_id` FROM `rk2`), StreakGrouping AS (SELECT `ws`.`player` AS `player`, `ws`.`is_win` AS `is_win`, `ws`.`date_played` AS `date_played`, row_number() over ( partition by `ws`.`player` order by `ws`.`date_played`,`ws`.`tee_colour`,`ws`.`score_id`) - row_number() over ( partition by `ws`.`player`,`ws`.`is_win` order by `ws`.`date_played`,`ws`.`tee_colour`,`ws`.`score_id`) AS `grp` FROM `WinSequence` AS `ws`), StreakStats AS (SELECT `sg`.`player` AS `player`, `sg`.`grp` AS `grp`, count(0) AS `streak_length`, min(`sg`.`date_played`) AS `start_date`, max(`sg`.`date_played`) AS `end_date` FROM `StreakGrouping` AS `sg` WHERE `sg`.`is_win` = 1 GROUP BY `sg`.`player`, `sg`.`grp`), LongestStreakPerPlayer AS (SELECT `ss`.`player` AS `player`, `ss`.`streak_length` AS `streak_length`, `ss`.`start_date` AS `start_date`, `ss`.`end_date` AS `end_date`, row_number() over ( partition by `ss`.`player` order by `ss`.`streak_length` desc,`ss`.`end_date` desc) AS `streak_rank` FROM `StreakStats` AS `ss`), LowestScoreRank AS (SELECT `p`.`name` AS `player_name`, `s`.`gross_score` AS `gross_score`, `s`.`date_played` AS `date_played`, row_number() over ( partition by `p`.`player_id` order by `s`.`gross_score`,`s`.`date_played` desc) AS `score_rank` FROM (`wp_golf_scores` `s` join `wp_golf_players` `p` on(`s`.`player_id` = `p`.`player_id`)))  SELECT `p`.`player_id` AS `player_id`, `p`.`name` AS `player_name`, `lsr`.`gross_score` AS `best_score`, `lsr`.`date_played` AS `best_date`, coalesce(`lsp`.`streak_length`,0) AS `streak_count`, `lsp`.`start_date` AS `streak_start`, `lsp`.`end_date` AS `streak_end` FROM ((`wp_golf_players` `p` left join `LowestScoreRank` `lsr` on(`p`.`name` = `lsr`.`player_name` and `lsr`.`score_rank` = 1)) left join `LongestStreakPerPlayer` `lsp` on(`p`.`name` = `lsp`.`player` and `lsp`.`streak_rank` = 1)))  ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_rolling_averages`
--
DROP TABLE IF EXISTS `view_golf_rolling_averages`;

DROP VIEW IF EXISTS `view_golf_rolling_averages`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_rolling_averages`  AS SELECT `ranked_history`.`player_id` AS `player_id`, `ranked_history`.`player_name` AS `player_name`, round(avg(`ranked_history`.`putts`),1) AS `avg_putts_20`, round(avg(`ranked_history`.`gir`),1) AS `avg_gir_20` FROM (select `wp_golf_dashboard_history`.`player_id` AS `player_id`,`wp_golf_dashboard_history`.`player_name` AS `player_name`,`wp_golf_dashboard_history`.`putts` AS `putts`,`wp_golf_dashboard_history`.`gir` AS `gir`,row_number() over ( partition by `wp_golf_dashboard_history`.`player_id` order by `wp_golf_dashboard_history`.`date_played` desc) AS `row_num` from `wp_golf_dashboard_history`) AS `ranked_history` WHERE `ranked_history`.`row_num` <= 20 GROUP BY `ranked_history`.`player_id`, `ranked_history`.`player_name` ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_rounds`
--
DROP TABLE IF EXISTS `view_golf_rounds`;

DROP VIEW IF EXISTS `view_golf_rounds`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_rounds`  AS SELECT `e`.`date_played` AS `date_played`, `e`.`tee_colour` AS `tee_colour`, max(`e`.`player_count`) AS `player_count`, min(`e`.`net_score`) AS `best_nett_score`, sum(case when `e`.`nett_position` = 1 then 1 else 0 end) AS `winners_count`, CASE WHEN sum(case when `e`.`nett_position` = 1 then 1 else 0 end) = 1 THEN max(case when `e`.`nett_position` = 1 then `e`.`player` end) ELSE NULL END AS `winner_player`, CASE WHEN sum(case when `e`.`nett_position` = 1 then 1 else 0 end) = 1 THEN max(case when `e`.`nett_position` = 1 then `p`.`winner_colour` end) ELSE NULL END AS `winner_colour` FROM (`view_golf_round_entries` `e` left join `wp_golf_players` `p` on(`p`.`name` = `e`.`player`)) GROUP BY `e`.`date_played`, `e`.`tee_colour` ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_rounds_pivot`
--
DROP TABLE IF EXISTS `view_golf_rounds_pivot`;

DROP VIEW IF EXISTS `view_golf_rounds_pivot`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_rounds_pivot`  AS SELECT `r`.`date_played` AS `date_played`, `r`.`tee_colour` AS `tee_colour`, CASE `winner` ELSE `r`.`winner_player` AS `end` END FROM ((`view_golf_rounds` `r` left join `wp_golf_dashboard_history` `h` on(`h`.`date_played` = `r`.`date_played` and `h`.`tee_colour` = `r`.`tee_colour`)) left join `wp_golf_players` `p` on(`p`.`player_id` = `h`.`player_id`)) GROUP BY `r`.`date_played`, `r`.`tee_colour`, `r`.`player_count`, `r`.`winners_count`, `r`.`winner_player`, `r`.`winner_colour` ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_round_entries`
--
DROP TABLE IF EXISTS `view_golf_round_entries`;

DROP VIEW IF EXISTS `view_golf_round_entries`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_round_entries`  AS WITH base AS (SELECT `v`.`score_id` AS `score_id`, `v`.`player` AS `player`, `v`.`date_played` AS `date_played`, `v`.`tee_colour` AS `tee_colour`, `v`.`gross_score` AS `gross_score`, `v`.`net_score` AS `net_score`, `v`.`current_index` AS `current_index` FROM `view_scoreboard` AS `v`), ranked AS (SELECT `b`.`score_id` AS `score_id`, `b`.`player` AS `player`, `b`.`date_played` AS `date_played`, `b`.`tee_colour` AS `tee_colour`, `b`.`gross_score` AS `gross_score`, `b`.`net_score` AS `net_score`, `b`.`current_index` AS `current_index`, rank() over ( partition by `b`.`date_played`,`b`.`tee_colour` order by `b`.`net_score`) AS `nett_position` FROM `base` AS `b`), with_counts AS (SELECT `r`.`score_id` AS `score_id`, `r`.`player` AS `player`, `r`.`date_played` AS `date_played`, `r`.`tee_colour` AS `tee_colour`, `r`.`gross_score` AS `gross_score`, `r`.`net_score` AS `net_score`, `r`.`current_index` AS `current_index`, `r`.`nett_position` AS `nett_position`, sum(case when `r`.`nett_position` = 1 then 1 else 0 end) over ( partition by `r`.`date_played`,`r`.`tee_colour`) AS `nett_winners_count`, count(0) over ( partition by `r`.`date_played`,`r`.`tee_colour`) AS `player_count` FROM `ranked` AS `r`) SELECT `wc`.`date_played` AS `date_played`, `wc`.`tee_colour` AS `tee_colour`, `wc`.`player` AS `player`, `wc`.`score_id` AS `score_id`, `wc`.`gross_score` AS `gross_score`, `wc`.`net_score` AS `net_score`, `wc`.`current_index` AS `hcp_index_start`, `wc`.`nett_position` AS `nett_position`, `wc`.`player_count` AS `player_count`, CASE WHEN `wc`.`nett_position` = 1 AND `wc`.`nett_winners_count` > 1 THEN 1 ELSE 0 END AS `is_draw_nett`, CASE WHEN `wc`.`nett_position` = 1 AND `wc`.`nett_winners_count` = 1 AND `wc`.`player_count` > 1 THEN 1 ELSE 0 END AS `is_win_nett` FROM `with_counts` AS `wc``wc`  ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_win_streaks`
--
DROP TABLE IF EXISTS `view_golf_win_streaks`;

DROP VIEW IF EXISTS `view_golf_win_streaks`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_win_streaks`  AS WITH rounds AS (SELECT `e`.`player` AS `player`, `e`.`date_played` AS `date_played`, `e`.`tee_colour` AS `tee_colour`, `e`.`score_id` AS `score_id`, `e`.`is_win_nett` AS `is_win_nett`, sum(case when `e`.`is_win_nett` = 0 then 1 else 0 end) over ( partition by `e`.`player` order by `e`.`date_played`,`e`.`tee_colour`,`e`.`score_id` rows between  unbounded  preceding and  current row ) AS `break_grp` FROM `view_golf_round_entries` AS `e`), wins AS (SELECT `r`.`player` AS `player`, `r`.`break_grp` AS `break_grp`, count(0) AS `streak_wins`, min(`r`.`score_id`) AS `first_score_id`, max(`r`.`score_id`) AS `last_score_id` FROM `rounds` AS `r` WHERE `r`.`is_win_nett` = 1 GROUP BY `r`.`player`, `r`.`break_grp`)  SELECT `w`.`player` AS `player`, `s1`.`date_played` AS `streak_start_date`, `s1`.`tee_colour` AS `streak_start_tee`, `s2`.`date_played` AS `streak_end_date`, `s2`.`tee_colour` AS `streak_end_tee`, `w`.`streak_wins` AS `streak_wins`, `w`.`first_score_id` AS `first_score_id`, `w`.`last_score_id` AS `last_score_id` FROM ((`wins` `w` join `view_golf_round_entries` `s1` on(`s1`.`score_id` = `w`.`first_score_id`)) join `view_golf_round_entries` `s2` on(`s2`.`score_id` = `w`.`last_score_id`)))  ;

-- --------------------------------------------------------

--
-- Structure for view `view_golf_yearly_stats`
--
DROP TABLE IF EXISTS `view_golf_yearly_stats`;

DROP VIEW IF EXISTS `view_golf_yearly_stats`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_golf_yearly_stats`  AS SELECT `p`.`name` AS `player_name`, year(`s`.`date_played`) AS `stat_year`, count(`s`.`score_id`) AS `total_rounds`, round(avg(`s`.`gross_score`),1) AS `avg_gross_year`, round(avg(`s`.`putts`),1) AS `avg_putts_year`, round(avg(`s`.`gir`),1) AS `avg_gir_year`, sum(case when `s`.`gross_score` < 80 then 1 else 0 end) AS `sub_80`, sum(case when `s`.`gross_score` between 80 and 84 then 1 else 0 end) AS `cat_80_84`, sum(case when `s`.`gross_score` between 85 and 89 then 1 else 0 end) AS `cat_85_89`, sum(case when `s`.`gross_score` between 90 and 99 then 1 else 0 end) AS `cat_90_99`, sum(case when `s`.`gross_score` >= 100 then 1 else 0 end) AS `cat_100_plus`, sum(case when `e`.`is_win_nett` = 1 and `e`.`player_count` > 1 then 1 else 0 end) AS `wins` FROM ((`wp_golf_scores` `s` join `wp_golf_players` `p` on(`p`.`player_id` = `s`.`player_id`)) left join `view_golf_round_entries` `e` on(`e`.`score_id` = `s`.`score_id`)) GROUP BY `p`.`name`, year(`s`.`date_played`) ;

-- --------------------------------------------------------

--
-- Structure for view `view_handicap_index`
--
DROP TABLE IF EXISTS `view_handicap_index`;

DROP VIEW IF EXISTS `view_handicap_index`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_handicap_index`  AS SELECT `p`.`player_id` AS `player_id`, `p`.`name` AS `player_name`, coalesce(`h`.`rounds_in_window`,0) AS `rounds_counted`, `h`.`hcp_after` AS `current_handicap_index`, `h`.`previous_hcp_after` AS `previous_handicap_index`, CASE WHEN `h`.`previous_hcp_after` is null THEN 'same' WHEN `h`.`hcp_after` > `h`.`previous_hcp_after` THEN 'up' WHEN `h`.`hcp_after` < `h`.`previous_hcp_after` THEN 'down' ELSE 'same' END AS `hi_direction` FROM (`wp_golf_players` `p` left join (select `last`.`player_id` AS `player_id`,`last`.`hcp_after` AS `hcp_after`,(select `prev`.`hcp_after` from (`wp_golf_handicap_history` `prev` join `wp_golf_scores` `ps` on(`prev`.`score_id` = `ps`.`score_id`)) where `prev`.`player_id` = `last`.`player_id` and `ps`.`tee_id` in (1,2,3) and (`prev`.`date_played` < `last`.`date_played` or `prev`.`date_played` = `last`.`date_played` and `prev`.`score_id` < `last`.`score_id`) order by `prev`.`date_played` desc,`prev`.`score_id` desc limit 1) AS `previous_hcp_after`,(select least(count(0),20) from (`wp_golf_handicap_history` `h2` join `wp_golf_scores` `s2` on(`h2`.`score_id` = `s2`.`score_id`)) where `h2`.`player_id` = `last`.`player_id` and `s2`.`tee_id` in (1,2,3) and (`h2`.`date_played` < `last`.`date_played` or `h2`.`date_played` = `last`.`date_played` and `h2`.`score_id` <= `last`.`score_id`)) AS `rounds_in_window` from (((`wp_golf_handicap_history` `last` join `wp_golf_scores` `s` on(`last`.`score_id` = `s`.`score_id`)) join (select `hh`.`player_id` AS `player_id`,max(`hh`.`date_played`) AS `max_date` from (`wp_golf_handicap_history` `hh` join `wp_golf_scores` `ss` on(`hh`.`score_id` = `ss`.`score_id`)) where `ss`.`tee_id` in (1,2,3) group by `hh`.`player_id`) `mx` on(`mx`.`player_id` = `last`.`player_id` and `mx`.`max_date` = `last`.`date_played`)) join (select `hh`.`player_id` AS `player_id`,`hh`.`date_played` AS `date_played`,max(`hh`.`score_id`) AS `max_score_id` from (`wp_golf_handicap_history` `hh` join `wp_golf_scores` `ss` on(`hh`.`score_id` = `ss`.`score_id`)) where `ss`.`tee_id` in (1,2,3) group by `hh`.`player_id`,`hh`.`date_played`) `ms` on(`ms`.`player_id` = `last`.`player_id` and `ms`.`date_played` = `last`.`date_played` and `ms`.`max_score_id` = `last`.`score_id`)) where `s`.`tee_id` in (1,2,3)) `h` on(`h`.`player_id` = `p`.`player_id`)) ;

-- --------------------------------------------------------

--
-- Structure for view `view_last_20_rounds`
--
DROP TABLE IF EXISTS `view_last_20_rounds`;

DROP VIEW IF EXISTS `view_last_20_rounds`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_last_20_rounds`  AS SELECT `view_round_differentials`.`player_id` AS `player_id`, `view_round_differentials`.`score_id` AS `score_id`, `view_round_differentials`.`differential` AS `differential` FROM `view_round_differentials` WHERE `view_round_differentials`.`recency_rank` <= 20 ;

-- --------------------------------------------------------

--
-- Structure for view `view_playing_handicaps`
--
DROP TABLE IF EXISTS `view_playing_handicaps`;

DROP VIEW IF EXISTS `view_playing_handicaps`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_playing_handicaps`  AS SELECT `vhi`.`player_id` AS `player_id`, `vhi`.`player_name` AS `player_name`, round(`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`),2) AS `white_exact`, round((`vhi`.`current_handicap_index` * (`tw`.`slope_rating` / 113) + (`tw`.`course_rating` - `tw`.`par`)) * 0.95,0) AS `white_play`, round(`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`),2) AS `yellow_exact`, round((`vhi`.`current_handicap_index` * (`ty`.`slope_rating` / 113) + (`ty`.`course_rating` - `ty`.`par`)) * 0.95,0) AS `yellow_play`, round(`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`),2) AS `black_exact`, round((`vhi`.`current_handicap_index` * (`tb`.`slope_rating` / 113) + (`tb`.`course_rating` - `tb`.`par`)) * 0.95,0) AS `black_play` FROM ((((`view_handicap_index` `vhi` left join `wp_golf_tees` `tw` on(`tw`.`tee_colour` = 'White')) left join `wp_golf_tees` `ty` on(`ty`.`tee_colour` = 'Yellow')) left join `wp_golf_tees` `tb` on(`tb`.`tee_colour` = 'Black')) join `wp_golf_courses` `c` on(`c`.`course_name` = 'Ramsey Golf Club')) WHERE `tw`.`course_id` = `c`.`course_id` AND `ty`.`course_id` = `c`.`course_id` AND `tb`.`course_id` = `c`.`course_id` ;

-- --------------------------------------------------------

--
-- Structure for view `view_round_differentials`
--
DROP TABLE IF EXISTS `view_round_differentials`;

DROP VIEW IF EXISTS `view_round_differentials`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_round_differentials`  AS SELECT `s`.`player_id` AS `player_id`, `s`.`score_id` AS `score_id`, `s`.`date_played` AS `date_played`, `s`.`gross_score` AS `gross_score`, round((`s`.`gross_score` - `t`.`course_rating` - coalesce(`s`.`pcc_adjustment`,0)) * 113 / `t`.`slope_rating`,1) AS `differential`, (select count(0) + 1 from `wp_golf_scores` `s2` where `s2`.`player_id` = `s`.`player_id` and `s2`.`is_excluded` = 0 and (`s2`.`date_played` > `s`.`date_played` or `s2`.`date_played` = `s`.`date_played` and `s2`.`score_id` > `s`.`score_id`)) AS `recency_rank` FROM (`wp_golf_scores` `s` join `wp_golf_tees` `t` on(`s`.`tee_id` = `t`.`tee_id`)) WHERE `s`.`is_excluded` = 0 ;

-- --------------------------------------------------------

--
-- Structure for view `view_scoreboard`
--
DROP TABLE IF EXISTS `view_scoreboard`;

DROP VIEW IF EXISTS `view_scoreboard`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `view_scoreboard`  AS SELECT `s`.`score_id` AS `score_id`, `p`.`name` AS `player`, `c`.`course_name` AS `course_name`, `t`.`tee_colour` AS `tee_colour`, `s`.`date_played` AS `date_played`, `s`.`gross_score` AS `gross_score`, coalesce(`hh`.`hcp_before`,54.0) AS `current_index`, `hh`.`playing_hcp` AS `playing_handicap`, `hh`.`net_score` AS `net_score`, `s`.`putts` AS `putts`, `s`.`gir` AS `gir`, `s`.`pcc_adjustment` AS `pcc_adjustment`, `hh`.`differential` AS `handicap_differential` FROM ((((`wp_golf_scores` `s` join `wp_golf_players` `p` on(`s`.`player_id` = `p`.`player_id`)) join `wp_golf_tees` `t` on(`s`.`tee_id` = `t`.`tee_id`)) join `wp_golf_courses` `c` on(`t`.`course_id` = `c`.`course_id`)) left join `wp_golf_handicap_history` `hh` on(`hh`.`score_id` = `s`.`score_id`)) ORDER BY `s`.`date_played` DESC ;

-- --------------------------------------------------------

--
-- Structure for view `wp_golf_dashboard_history`
--
DROP TABLE IF EXISTS `wp_golf_dashboard_history`;

DROP VIEW IF EXISTS `wp_golf_dashboard_history`;
CREATE OR REPLACE ALGORITHM=UNDEFINED DEFINER=`u271511030_AFpgR`@`127.0.0.1` SQL SECURITY DEFINER VIEW `wp_golf_dashboard_history`  AS SELECT `s`.`score_id` AS `score_id`, `s`.`date_played` AS `date_played`, `s`.`player_id` AS `player_id`, `p`.`name` AS `player_name`, `s`.`tee_id` AS `tee_id`, `t`.`tee_colour` AS `tee_colour`, `s`.`gross_score` AS `gross_score`, `s`.`pcc_adjustment` AS `pcc_adjustment`, `h`.`hcp_before` AS `index`, `h`.`hcp_before` AS `starting_index`, `h`.`playing_hcp` AS `playing_hcp`, `h`.`net_score` AS `net_score`, `h`.`differential` AS `differential`, `s`.`putts` AS `putts`, `s`.`gir` AS `gir`, `h`.`is_best_8` AS `is_counting`, CASE WHEN `h`.`cap_type` is not null AND `h`.`cap_type` <> 'NONE' THEN 1 ELSE 0 END AS `cap_applied`, CASE WHEN `h`.`esr_triggered` = 1 THEN 1 ELSE 0 END AS `esr_applied`, `h`.`cap_type` AS `cap_type`, `h`.`cap_reduction` AS `cap_reduction`, `h`.`esr_triggered` AS `esr_triggered`, `h`.`esr_amount` AS `esr_amount`, `s`.`is_excluded` AS `is_excluded` FROM (((`wp_golf_scores` `s` join `wp_golf_players` `p` on(`p`.`player_id` = `s`.`player_id`)) join `wp_golf_tees` `t` on(`t`.`tee_id` = `s`.`tee_id`)) left join `wp_golf_handicap_history` `h` on(`h`.`score_id` = `s`.`score_id`)) ;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
