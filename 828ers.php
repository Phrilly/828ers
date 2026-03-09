<?php
/**
 * Plugin Name: 828ers Golf System
 * Description: WHS handicap tracking and dashboards for the 828ers group.
 * Version: 1.0
 * Author: Phrilly
 */

if ( ! defined( 'ABSPATH' ) ) exit;

// Load individual PHP files
require_once plugin_dir_path(__FILE__) . 'includes/Golf Master System.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Stats Dashboard.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Rounds Pivot.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Round History.php';
require_once plugin_dir_path(__FILE__) . 'includes/Download Excel Sheet.php';
require_once plugin_dir_path(__FILE__) . 'includes/Handicap Index Chart.php';
require_once plugin_dir_path(__FILE__) . 'includes/Show admin bar.php';

add_action('wp_enqueue_scripts', function () {
    $base_url  = plugin_dir_url(__FILE__);
    $base_path = plugin_dir_path(__FILE__);

    // CSS files in load order — each depends on the previous
    $css_files = [
        '828ers-globals'    => 'assets/golf-globals.css',
        '828ers-dashboard'  => 'assets/golf-dashboard.css',
        '828ers-history'    => 'assets/golf-history.css',
        '828ers-pagination' => 'assets/golf-pagination.css',
        '828ers-pivot'      => 'assets/golf-pivot.css',
        '828ers-forms'      => 'assets/golf-forms.css',
        '828ers-mobile'     => 'assets/golf-mobile.css',
    ];

    $prev_handle = array();
    foreach ( $css_files as $handle => $rel_path ) {
        $ver = file_exists( $base_path . $rel_path ) ? filemtime( $base_path . $rel_path ) : '1.0';
        wp_enqueue_style( $handle, $base_url . $rel_path, $prev_handle, $ver );
        $prev_handle = array( $handle );
    }

    // JavaScript (unchanged)
    $js_rel = 'assets/js/unified_javascript.js';
    $js_ver = file_exists( $base_path . $js_rel ) ? filemtime( $base_path . $js_rel ) : '1.0';

    wp_enqueue_script(
        '828ers-js',
        $base_url . $js_rel,
        array('jquery'),
        $js_ver,
        true
    );

    wp_localize_script('828ers-js', 'GolfMasterAjax', [
        'ajaxUrl' => admin_url('admin-ajax.php'),
        'nonce'   => wp_create_nonce('golf_master_nonce'),
    ]);
});
