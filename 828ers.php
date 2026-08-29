<?php
/**
 * Plugin Name: 828ers Golf Handicap System
 * Description: Automated WHS Handicap Tracking, Dashboards, and Git-Triggered Migrations.
 * Version:     1.1.28
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
require_once plugin_dir_path(__FILE__) . 'includes/Golf_Hole_by_Hole.php';
require_once plugin_dir_path(__FILE__) . 'includes/eBay iPhone Listings.php';
require_once plugin_dir_path(__FILE__) . 'includes/Golf Eclectic.php';

// ==========================================
// 2. FRONTEND: Enqueue CSS & JS
// ==========================================
add_action('wp_enqueue_scripts', function () {
    $base_url  = plugin_dir_url(__FILE__);
    $base_path = plugin_dir_path(__FILE__);

    $css_files = [
        '828ers-globals'       => 'assets/css/golf-globals.css',
        '828ers-dashboard'     => 'assets/css/golf-dashboard.css',
        '828ers-history'       => 'assets/css/golf-history.css',
        '828ers-pagination'    => 'assets/css/golf-pagination.css',
        '828ers-pivot'         => 'assets/css/golf-pivot.css',
        '828ers-forms'         => 'assets/css/golf-forms.css',
        '828ers-whatif'        => 'assets/css/golf-whatif.css',
        '828ers-mobile'        => 'assets/css/golf-mobile.css',
        '828ers-hole-analysis' => 'assets/css/golf-hole-analysis.css',
        '828ers-ebay-listings' => 'assets/css/ebay-listings.css',
        '828ers-eclectic' => 'assets/css/golf-eclectic.css',
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
function golf_migration_write_audit_log($audit_log) {
    $timestamp = gmdate('Y-m-d H:i:s T');
    $payload = implode("\n", $audit_log);
    update_option('golf_migration_audit_log', $timestamp . "\n" . $payload);
}

function golf_migration_log_context(&$audit_log, $label = 'RUN') {
    global $wpdb;

    $db_name = $wpdb->get_var('SELECT DATABASE()');
    $db_user = $wpdb->get_var('SELECT USER()');
    $db_version = $wpdb->get_var('SELECT VERSION()');
    $db_host = defined('DB_HOST') ? DB_HOST : 'unknown';
    $table_prefix = isset($wpdb->prefix) ? $wpdb->prefix : 'unknown';

    $audit_log[] = "DB CONTEXT: {$label} timestamp=" . gmdate('Y-m-d H:i:s T')
        . " db_name=" . (string) $db_name
        . " db_user=" . (string) $db_user
        . " db_host=" . (string) $db_host
        . " table_prefix=" . (string) $table_prefix
        . " server_version=" . (string) $db_version;
}

function golf_migration_log_procedure_state(&$audit_log, $procedure_name, $phase) {
    global $wpdb;

    if (empty($procedure_name)) {
        return;
    }

    $exists = $wpdb->get_var(
        $wpdb->prepare(
            "SELECT COUNT(*) FROM information_schema.routines WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE' AND ROUTINE_NAME = %s",
            $procedure_name
        )
    );

    $audit_log[] = "PROC STATE: {$phase} `{$procedure_name}` -> exists=" . (int) $exists;
}

// 3. BACKEND: Database Migration Pipeline
// ==========================================
function golf_system_run_migrations() {
    static $migration_has_started = false;

    if ($migration_has_started) {
        return;
    }

    $migration_has_started = true;

    global $wpdb;
    $installed_ver = get_option('golf_plugin_db_version');

    if ($installed_ver !== GOLF_PLUGIN_VERSION) {
        clearstatcache();
        $sql_dir = plugin_dir_path(__FILE__) . 'sql/';
        $files = glob($sql_dir . '*.sql');

        $audit_log = [];

        if (empty($files)) {
            $audit_log[] = "CRITICAL FAIL: No .sql files found in directory: " . $sql_dir;
            golf_migration_write_audit_log($audit_log);
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
            'view_eclectic.sql',
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
        golf_migration_log_context($audit_log, 'MIGRATION_START');
        $audit_log[] = "PLUGIN VERSION: " . GOLF_PLUGIN_VERSION . " | INSTALLED DB VERSION: " . (string) $installed_ver;

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
                $audit_log[] = "EXEC: Block {$block_num} START timestamp=" . gmdate('Y-m-d H:i:s T') . " preview=" . $preview;

                $procedure_name = null;
                if (preg_match('/^\s*DROP\s+PROCEDURE\s+IF\s+EXISTS\s+`?([A-Za-z0-9_]+)`?/i', $query, $matches)) {
                    $procedure_name = $matches[1];
                    golf_migration_log_procedure_state($audit_log, $procedure_name, 'before drop');
                } elseif (preg_match('/^\s*CREATE\s+PROCEDURE\s+`?([A-Za-z0-9_]+)`?/i', $query, $matches)) {
                    $procedure_name = $matches[1];
                    golf_migration_log_procedure_state($audit_log, $procedure_name, 'before create');
                }

                $result = $wpdb->query($query);
                $db_error = $wpdb->last_error;

                if ($procedure_name !== null) {
                    if ($result !== false) {
                        golf_migration_log_procedure_state($audit_log, $procedure_name, 'after execute');
                    } elseif (stripos((string) $db_error, 'already exists') !== false) {
                        golf_migration_log_procedure_state($audit_log, $procedure_name, 'after failed create');
                    }
                }

                if (
                    $result === false
                    && preg_match('/^\s*CREATE\s+PROCEDURE\s+`?([A-Za-z0-9_]+)`?/i', $query, $matches)
                    && stripos((string) $db_error, 'already exists') !== false
                ) {
                    $procedure_name = $matches[1];
                    $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> CREATE PROCEDURE already exists; attempting DROP and retry for `{$procedure_name}`.";

                    $drop_result = $wpdb->query("DROP PROCEDURE IF EXISTS `{$procedure_name}`");
                    $drop_error = $wpdb->last_error;

                    golf_migration_log_procedure_state($audit_log, $procedure_name, 'after explicit drop before retry');

                    if ($drop_result !== false) {
                        $result = $wpdb->query($query);
                        $db_error = $wpdb->last_error;

                        if ($result === false) {
                            $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> RETRY FAILED after DROP. DB Error: {$db_error}";
                            golf_migration_log_procedure_state($audit_log, $procedure_name, 'after failed retry create');
                        } else {
                            $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> RETRY SUCCESS after DROP. Rows affected: {$result}";
                            golf_migration_log_procedure_state($audit_log, $procedure_name, 'after successful retry create');
                        }
                    } else {
                        $db_error = $drop_error;
                        $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> DROP before retry failed. DB Error: {$db_error}";
                    }
                }

                if ($result === false) {
                    $audit_log[] = "EXEC: Block {$block_num} [{$preview}] -> HARD FAIL. DB Error: {$db_error}";
                    golf_migration_write_audit_log($audit_log);
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
        golf_migration_write_audit_log($audit_log);
        delete_option('golf_migration_last_error');
    }
}

add_action('plugins_loaded', 'golf_system_run_migrations');
add_action('admin_init', 'golf_system_run_migrations');

// ==========================================
// EBAY: Marketplace Account Deletion Endpoint
// ==========================================
add_action('rest_api_init', function () {
    register_rest_route('828ers/v1', '/ebay-deletion', [
        'methods'             => ['GET', 'POST'],
        'callback'            => 'ebay_deletion_handler',
        'permission_callback' => '__return_true',
    ]);
});

function ebay_deletion_handler(WP_REST_Request $request) {
    $challenge = $request->get_param('challenge_code');
    if ($challenge) {
        $verification_token = '828ers_ebay_verify_2026_26011965'; // must match exactly what you entered in eBay dashboard
        $endpoint_url       = 'https://828ers.im/wp-json/828ers/v1/ebay-deletion';
        $hash = hash('sha256', $challenge . $verification_token . $endpoint_url);
        return new WP_REST_Response(['challengeResponse' => $hash], 200);
    }
    return new WP_REST_Response(['acknowledged' => true], 200);
}