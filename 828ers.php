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
    wp_enqueue_style('828ers-css', plugin_dir_url(__FILE__) . 'assets/css/unified_css.css');
    wp_enqueue_script('828ers-js', plugin_dir_url(__FILE__) . 'assets/js/unified_javascript.js', array(), '1.0', true);
});