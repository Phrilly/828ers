<?php
/* ======================================================
   HERO IMAGE UPDATER FOR DIVI DYNAMIC CONTENT
   (Bulletproof Cache-Clearing & Admin Trigger Version)
   ====================================================== */

if ( ! defined( 'ABSPATH' ) ) exit;

// 1. Run on frontend page loads
add_action('wp', 'golf_trigger_hero_update_frontend');
function golf_trigger_hero_update_frontend() {
    if (is_front_page()) {
        golf_update_latest_winner_hero_image();
    }
}

// 2. Run whenever the WordPress Admin is loaded (Bulletproof trigger)
add_action('admin_init', 'golf_update_latest_winner_hero_image');

function golf_update_latest_winner_hero_image() {
    global $wpdb;
    
    // Get the exact ID of the designated Homepage
    $homepage_id = (int) get_option('page_on_front');
    if (!$homepage_id) return;

    $scores_table = $wpdb->prefix . 'golf_scores';

    // Find the date of the most recent competitive round
    $latest_comp_date = $wpdb->get_var("
        SELECT s.date_played
        FROM {$scores_table} s
        JOIN view_golf_round_entries e ON e.score_id = s.score_id
        WHERE e.player_count > 1
        ORDER BY s.date_played DESC
        LIMIT 1
    ");

    if (!$latest_comp_date) return;

    // Get all winners from that specific date
    $winners = $wpdb->get_col($wpdb->prepare("
        SELECT s.player_id
        FROM {$scores_table} s
        JOIN view_golf_round_entries e ON e.score_id = s.score_id
        WHERE s.date_played = %s AND e.is_win_nett = 1 AND e.player_count > 1
    ", $latest_comp_date));

    $winner_count = count($winners);
    if ($winner_count === 0) return;

    // Determine if single winner or tie
    $image_key = ($winner_count > 1) ? 'tie' : (int) $winners[0];

    // Map keys to Hero Image URLs
    $hero_images = [
        1 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Fluked-One.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Fluked-Portrait.png' 
        ],
        2 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Proper_Golfer.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Proper-Portrait.png' 
        ],
        3 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Peoples-Champ.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Peoples-Portrait.png' 
        ],
        4 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Adder.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Adder-Portrait.png' 
        ],
        'tie' => [ // Add your tie image URLs here later!
            'landscape' => 'https://828ers.im/wp-content/uploads/YOUR_TIE_LANDSCAPE.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/YOUR_TIE_PORTRAIT.png' 
        ],
    ];

    $winner_pair = isset($hero_images[$image_key]) ? $hero_images[$image_key] : null;
    if (empty($winner_pair)) return;

    $changed = false;

    // Check and Update Landscape Field
    $new_l_url = $winner_pair['landscape'];
    $current_l = get_post_meta($homepage_id, 'latest_winner_hero_landscape', true);
    if ($current_l !== $new_l_url) {
        update_post_meta($homepage_id, 'latest_winner_hero_landscape', $new_l_url);
        $changed = true;
    }

    // Check and Update Portrait Field
    $new_p_url = $winner_pair['portrait'];
    $current_p = get_post_meta($homepage_id, 'latest_winner_hero_portrait', true);
    if ($current_p !== $new_p_url) {
        update_post_meta($homepage_id, 'latest_winner_hero_portrait', $new_p_url);
        $changed = true;
    }

    // CRITICAL: If the image changed, force Divi and LiteSpeed to dump their caches!
    if ($changed) {
        // 1. Wipe Divi's internal CSS hash reference for the homepage
        update_post_meta($homepage_id, '_et_pb_static_css_file_hash', '');
        
        // 2. Trigger Divi's official cache clear function
        if (function_exists('et_core_clear_page_cache')) {
            et_core_clear_page_cache($homepage_id);
        }
        
        // 3. Trigger LiteSpeed cache clear for the homepage
        if (defined('LSCWP_V') && function_exists('do_action')) {
            do_action('litespeed_purge_post', $homepage_id);
        }
    }
}