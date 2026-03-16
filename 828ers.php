<?php
/*
Plugin Name: 828ers Golf Handicap System
Description: Automated WHS Handicap Tracking with Git-Triggered Migrations.
Version:     1.0.9
Author:      Philip Dunne
*/

// Define version for cache busting and migration tracking
define('GOLF_PLUGIN_VERSION', '1.0.9');

/**
 * 828ers Migration Engine
 * Automatically syncs the /sql/ folder to the database on version bump.
 */
function golf_system_run_migrations() {
    global $wpdb;

    // Check if we actually need to run
    $installed_ver = get_option('golf_plugin_db_version');

    if ($installed_ver !== GOLF_PLUGIN_VERSION) {
        $sql_dir = plugin_dir_path(__FILE__) . 'sql/';
        
        // 1. Get ALL .sql files in the folder
        $files = glob($sql_dir . '*.sql');

        if (!empty($files)) {
            // Sort files so they run in alphabetical order
            sort($files); 

            foreach ($files as $file_path) {
                if (file_exists($file_path)) {
                    $sql_contents = file_get_contents($file_path);

                    // 2. Clean up MySQL specific bloat
                    $sql_contents = preg_replace('/DELIMITER\s+\S+/i', '', $sql_contents);
                    $sql_contents = preg_replace('/DEFINER\s*=\s*`[^`]+`@`[^`]+`/', '', $sql_contents);
                    $sql_contents = str_replace('$$', ';', $sql_contents);

                    // 3. Split by your -- END_QUERY marker
                    $queries = preg_split('/--\s*END_QUERY\s*/i', $sql_contents);

                    foreach ($queries as $query) {
                        $query = trim($query);
                        if (!empty($query)) {
                            // 4. Execute and log errors if they occur
                            $result = $wpdb->query($query);
                            if ($result === false) {
                                error_log("828ers Migration failed in " . basename($file_path) . ": " . $wpdb->last_error);
                            }
                        }
                    }
                }
            }
        }

        // 5. Record the successful move to the new version
        update_option('golf_plugin_db_version', GOLF_PLUGIN_VERSION);
    }
}

// Trigger the migration engine when entering the WordPress Admin
add_action('admin_init', 'golf_system_run_migrations');