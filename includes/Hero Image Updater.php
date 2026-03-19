<?php
/* ======================================================
   HERO IMAGE UPDATER FOR DIVI DYNAMIC CONTENT
   (Dual Orientation, Handles Ties & Ignores Solo Rounds)
   ====================================================== */

if ( ! defined( 'ABSPATH' ) ) exit;

add_action('wp', 'golf_update_latest_winner_hero_image');

function golf_update_latest_winner_hero_image() {
    // Only run this logic when someone visits the front page
    if (!is_front_page()) return;

    global $wpdb;
    $scores_table = $wpdb->prefix . 'golf_scores';

    // 1. Find the date of the most recent competitive round (ignores solo rounds!)
    $latest_comp_date = $wpdb->get_var("
        SELECT s.date_played
        FROM {$scores_table} s
        JOIN view_golf_round_entries e ON e.score_id = s.score_id
        WHERE e.player_count > 1
        ORDER BY s.date_played DESC
        LIMIT 1
    ");

    if (!$latest_comp_date) return;

    // 2. Get all winners from that specific date
    $winners = $wpdb->get_col($wpdb->prepare("
        SELECT s.player_id
        FROM {$scores_table} s
        JOIN view_golf_round_entries e ON e.score_id = s.score_id
        WHERE s.date_played = %s AND e.is_win_nett = 1 AND e.player_count > 1
    ", $latest_comp_date));

    $winner_count = count($winners);
    if ($winner_count === 0) return;

    // 3. Determine if it's a single winner or a tie
    $image_key = ($winner_count > 1) ? 'tie' : (int) $winners[0];

    // 4. Map keys to Hero Image URLs (Pairs: Landscape & Portrait)
    $hero_images = [
        1 => [ // PLAYER 1 (Phil D)
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Fluked-One.png',
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Fluked-Portrait.png',
        ],
        2 => [ // PLAYER 2 (Phil B)
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Proper_Golfer.png',
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Proper-Portrait.png',
        ],
        3 => [ // PLAYER 3
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Peoples-Champ.png',
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Peoples-Portrait.png',
        ],
        4 => [ // PLAYER 4
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Adder.png',
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Adder-Portrait.png',
        ],
        'tie' => [ // STANDARD IMAGE FOR TIED ROUNDS (ADD YOUR URLS HERE)
            'landscape' => 'https://828ers.im/wp-content/uploads/YOUR_TIE_LANDSCAPE.png',
            'portrait'  => 'https://828ers.im/wp-content/uploads/YOUR_TIE_PORTRAIT.png',
        ],
    ];

    $winner_pair = isset($hero_images[$image_key]) ? $hero_images[$image_key] : null;

    if (empty($winner_pair)) return;

    $homepage_id = get_queried_object_id();

    // 5. Update Custom Field A: Landscape (Desktop/Divi Base View)
    $new_l_url   = $winner_pair['landscape'];
    $current_l   = get_post_meta($homepage_id, 'latest_winner_hero_landscape', true);
    if ($current_l !== $new_l_url) {
        update_post_meta($homepage_id, 'latest_winner_hero_landscape', $new_l_url);
    }

    // 6. Update Custom Field B: Portrait (Mobile View)
    $new_p_url   = $winner_pair['portrait'];
    $current_p   = get_post_meta($homepage_id, 'latest_winner_hero_portrait', true);
    if ($current_p !== $new_p_url) {
        update_post_meta($homepage_id, 'latest_winner_hero_portrait', $new_p_url);
    }
}