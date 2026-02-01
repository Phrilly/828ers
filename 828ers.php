<?php
/**
 * Plugin Name: 828ers Golf System
 * Description: WHS handicap tracking and dashboards for the 828ers group.
 * Version: 1.0
 * Author: Phrilly
 */

// Load all your individual PHP files
require_once plugin_dir_path(__FILE__) . 'includes/Golf Master System.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Stats Dashboard.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Rounds Pivot.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Round History.php';
require_once plugin_dir_path(__FILE__) . 'includes/Download Excel Sheet.php';
require_once plugin_dir_path(__FILE__) . 'includes/Handicap Index Chart.php';
require_once plugin_dir_path(__FILE__) . 'includes/Show admin bar.php';

// Load your CSS and JS (front-end)
add_action('wp_enqueue_scripts', function () {
    $base_url  = plugin_dir_url(__FILE__);
    $base_path = plugin_dir_path(__FILE__);

    $css_rel = 'assets/css/unified_css.css';
    $js_rel  = 'assets/js/unified_javascript.js';

    $css_path = $base_path . $css_rel;
    $js_path  = $base_path . $js_rel;

    $css_ver = file_exists($css_path) ? filemtime($css_path) : null;
    $js_ver  = file_exists($js_path)  ? filemtime($js_path)  : null;

    wp_enqueue_style(
        '828ers-css',
        $base_url . $css_rel,
        array(),
        $css_ver
    );

    wp_enqueue_script(
        '828ers-js',
        $base_url . $js_rel,
        array('jquery'),
        $js_ver,
        true
    );
});
