<?php
/**
 * Plugin Name: 828ers Golf System
 * Description: WHS handicap tracking and dashboards for the 828ers group.
 * Version: 1.0
 * Author: Phrilly
 */

// Load all your individual PHP files
require_once plugin_dir_path(__FILE__) . 'Golf Master System.php';
require_once plugin_dir_path(__FILE__) . 'Golf Stats Dashboard.php';
require_once plugin_dir_path(__FILE__) . 'Golf Rounds Pivot.php';
require_once plugin_dir_path(__FILE__) . 'Golf Round History.php';
require_once plugin_dir_path(__FILE__) . 'Download Excel Sheet.php';
require_once plugin_dir_path(__FILE__) . 'Handicap Index Chart.php';
require_once plugin_dir_path(__FILE__) . 'Show admin bar.php';

// Load your CSS and JS (This makes them work on the front-end)
add_action('wp_enqueue_scripts', function() {
    wp_enqueue_style('828ers-css', plugin_dir_url(__FILE__) . 'Unified CSS.css');
    wp_enqueue_script('828ers-js', plugin_dir_url(__FILE__) . 'Unified JavaScript.js', array(), '1.0', true);
});