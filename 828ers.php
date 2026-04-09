<?php
/**
 * Plugin Name: 828ers Golf Handicap System
 * Description: Automated WHS Handicap Tracking, Dashboards, and Git-Triggered Migrations.
 * Version:     1.0.85
 * Author:      Philip Dunne
 */

if ( ! defined( 'ABSPATH' ) ) exit;

// ==========================================
// AUTO-VERSIONING: Read from the header above
// ==========================================
if ( ! defined( 'GOLF_PLUGIN_VERSION' ) ) {
    $plugin_data = get_file_data( __FILE__, array( 'Version' => 'Version' ), 'plugin' );
    define( 'GOLF_PLUGIN_VERSION', $plugin_data['Version'] );
}

// ==========================================
// 1. FRONTEND: Load Modules & Dashboards
// ==========================================
require_once plugin_dir_path(__FILE__) . 'includes/Golf Master System.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Stats Dashboard.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Rounds Pivot.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Round History.php';
require_once plugin_dir_path(__FILE__) . 'includes/Download Excel Sheet.php';
require_once plugin_dir_path(__FILE__) . 'includes/Handicap Index Chart.php';
require_once plugin_dir_path(__FILE__) . 'includes/Show admin bar.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf What If.php';
require_once plugin_dir_path(__FILE__) . 'includes/Hero Image Updater.php';
require_once plugin_dir_path(__FILE__) . 'includes/Rebuild_All_Players.php';

// ==========================================
// 2. FRONTEND: Enqueue CSS & JS
// ==========================================
add_action('wp_enqueue_scripts', function () {
    $base_url  = plugin_dir_url(__FILE__);
    $base_path = plugin_dir_path(__FILE__);

    $css_files = [
        '828ers-globals'    => 'assets/css/golf-globals.css',
        '828ers-dashboard'  => 'assets/css/golf-dashboard.css',
        '828ers-history'    => 'assets/css/golf-history.css',
        '828ers-pagination' => 'assets/css/golf-pagination.css',
        '828ers-pivot'      => 'assets/css/golf-pivot.css',
        '828ers-forms'      => 'assets/css/golf-forms.css',
        '828ers-whatif'     => 'assets/css/golf-whatif.css',
        '828ers-mobile'     => 'assets/css/golf-mobile.css',
    ];

    $prev_handle = array();
    foreach ( $css_files as $handle => $rel_path ) {
        $ver = file_exists( $base_path . $rel_path ) ? filemtime( $base_path . $rel_path ) : GOLF_PLUGIN_VERSION;
        wp_enqueue_style( $handle, $base_url . $rel_path, $prev_handle, $ver );
        $prev_handle = array( $handle );
    }

    $js_rel = 'assets/js/unified_javascript.js';
    $js_ver = file_exists( $base_path . $js_rel ) ? filemtime( $base_path . $js_rel ) : GOLF_PLUGIN_VERSION;

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

// ==========================================
// 3. BACKEND: Database Migration Pipeline
// ==========================================
function golf_system_run_migrations() {
    global $wpdb;
    $installed_ver = get_option('golf_plugin_db_version');

    if ($installed_ver !== GOLF_PLUGIN_VERSION) {
        clearstatcache();
        $sql_dir = plugin_dir_path(__FILE__) . 'sql/';
        $files = glob($sql_dir . '*.sql');

        $audit_log = [];

        if (empty($files)) {
            $audit_log[] = "CRITICAL FAIL: No .sql files found in directory: " . $sql_dir;
            update_option('golf_migration_audit_log', implode("\n", $audit_log));
            return;
        }

        // Sort alphabetically first
        sort($files);

        // --- DEPENDENCY MANAGEMENT OVERRIDE ---
        // Views that depend on other views go here — they will always run last, in order.
        $run_last = [
            'view_golf_daily_winners.sql',
            'view_golf_rolling_averages.sql',
            'view_golf_yearly_stats.sql',
        ];

        foreach ($run_last as $dep_file) {
            $full_path = $sql_dir . $dep_file;
            if (($key = array_search($full_path, $files)) !== false) {
                unset($files[$key]);
                $files[] = $full_path;
            }
        }

        // Re-index after unsets
        $files = array_values($files);
        // --------------------------------------

        $audit_log[] = "INIT: Found " . count($files) . " files. Starting processing...";

        $wpdb->hide_errors();

        foreach ($files as $file_path) {
            $filename = basename($file_path);
            $sql_contents = file_get_contents($file_path);

            $audit_log[] = "--- FILE: {$filename} (Size: " . strlen($sql_contents) . " bytes) ---";

            $sql_contents = preg_replace('/DELIMITER\s+\S+\s*/i', '', $sql_contents);
            $sql_contents = preg_replace('/DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*/i', '', $sql_contents);
            $sql_contents = str_replace('$$', '', $sql_contents);

            $queries = preg_split('/--\s*END_QUERY\s*/i', $sql_contents);
            $audit_log[] = "PARSER: Split into " . count($queries) . " potential query blocks.";

            $block_num = 1;
            foreach ($queries as $query) {
                $query = trim($query);
                if (empty($query)) {
                    $audit_log[] = "EXEC: Block {$block_num} skipped (Empty space).";
                    $block_num++;
                    continue;
                }

                $preview = substr(str_replace("\n", " ", $query), 0, 30) . "...";

                $result = $wpdb->query($query);
                $db_error = $wpdb->last_error;

                if ($result === false) {
                    $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> HARD FAIL. DB Error: {$db_error}";
                    update_option('golf_migration_audit_log', implode("\n", $audit_log));
                    return;
                } else {
                    if (!empty($db_error)) {
                        $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> SILENT FAIL. Hidden Error: {$db_error}";
                    } else {
                        $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> SUCCESS. Rows affected: {$result}";
                    }
                }
                $block_num++;
            }
        }

        update_option('golf_plugin_db_version', GOLF_PLUGIN_VERSION);
        $audit_log[] = "COMPLETED: Version successfully bumped to " . GOLF_PLUGIN_VERSION;
        update_option('golf_migration_audit_log', implode("\n", $audit_log));
        delete_option('golf_migration_last_error');
    }
}

add_action('admin_init', 'golf_system_run_migrations');