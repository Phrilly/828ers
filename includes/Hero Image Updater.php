<?php
/* ======================================================
   HERO IMAGE UPDATER FOR DIVI DYNAMIC CONTENT
   (Hardcoded to Page 53, Fixed SQL Queries)
   ====================================================== */

if ( ! defined( 'ABSPATH' ) ) exit;

// 1. Run on frontend page loads
add_action('wp', 'golf_trigger_hero_update_frontend');
function golf_trigger_hero_update_frontend() {
    // Fire if it's the front page OR if we are looking directly at Page 53
    if (is_front_page() || get_queried_object_id() == 53) {
        golf_update_latest_winner_hero_image();
    }
}

// 2. Run whenever the WordPress Admin is loaded
add_action('admin_init', 'golf_update_latest_winner_hero_image');

function golf_update_latest_winner_hero_image() {
    global $wpdb;

    // Hardcoded to your exact homepage ID to bypass WordPress routing quirks
    $homepage_id = 53;

    // 1. Find the date of the most recent competitive round (more than 1 player)
    $latest_comp_date = $wpdb->get_var("
        SELECT date_played
        FROM view_golf_dashboard_history
        GROUP BY date_played
        HAVING COUNT(DISTINCT player_id) > 1
        ORDER BY date_played DESC
        LIMIT 1
    ");

    if (!$latest_comp_date) return;

    // 2. Find the winning player(s) on that date (Lowest Net Score = Winner)
    $winners = $wpdb->get_col($wpdb->prepare("
        SELECT player_id
        FROM view_golf_dashboard_history
        WHERE date_played = %s
        AND net_score = (
            SELECT MIN(net_score)
            FROM view_golf_dashboard_history
            WHERE date_played = %s
        )
    ", $latest_comp_date, $latest_comp_date));

    $winner_count = count($winners);
    if ($winner_count === 0) return;

    // 3. Determine if single winner or tie
    $image_key = ($winner_count > 1) ? 'tie' : (int) $winners[0];

    // 4. Map keys to Hero Image URLs
    $hero_images = [
        1 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Fluked-One.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Fluked-Portrait.png' 
        ],
        2 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Proper-Golfer.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Proper-Portrait.png' 
        ],
        3 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/06/Jays-Missing-Portrait.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/06/Jays-Missing-Landscape.png' 
        ],
        4 => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/03/Adder.png', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/03/Adder-Portrait.png' 
        ],
        'tie' => [ 
            'landscape' => 'https://828ers.im/wp-content/uploads/2026/01/background5.jpg', 
            'portrait'  => 'https://828ers.im/wp-content/uploads/2026/01/background6.jpg' 
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
