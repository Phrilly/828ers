<?php
/*
Plugin Name: 828ers Golf Handicap System
Description: Automated WHS Handicap Tracking with Git-Triggered Migrations.
Version:     1.0.20
Author:      Philip Dunne
*/

// 1. Version definition (Engine only runs if this number changes)
define('GOLF_PLUGIN_VERSION', '1.0.20');

/**
 * 828ers Migration Engine
 * This function syncs the /sql/ sub-folder to the database.
 */
function golf_system_run_migrations() {
    global $wpdb;

    // Check if we actually need to run
    $installed_ver = get_option('golf_plugin_db_version');

    if ($installed_ver !== GOLF_PLUGIN_VERSION) {
        // Define the absolute path to the sql folder
        $sql_dir = plugin_dir_path(__FILE__) . 'sql/';
        
        // Use glob to find all .sql files
        $files = glob($sql_dir . '*.sql');

        // ERROR CHECK: If no files are found, log the path so we can debug it
        if (empty($files)) {
            update_option('golf_migration_last_error', "No SQL files found in: " . $sql_dir);
            // We do not return here; we allow the version to stay old so we can fix the path
        } else {
            // Sort files alphabetically to ensure correct order
            sort($files); 

            foreach ($files as $file_path) {
                if (file_exists($file_path)) {
                    $sql_contents = file_get_contents($file_path);

                    // Strip DELIMITER and DEFINER tags (they are for CLI/DBeaver, not PHP)
                    $sql_contents = preg_replace('/DELIMITER\s+\S+\s*/i', '', $sql_contents);
                    $sql_contents = preg_replace('/DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*/i', '', $sql_contents);

                    // Split ONLY by our custom marker to protect BEGIN...END blocks
                    $queries = preg_split('/--\s*END_QUERY\s*/i', $sql_contents);

                    foreach ($queries as $query) {
                        $query = trim($query);
                        if (!empty($query)) {
                            $result = $wpdb->query($query);
                            
                            if ($result === false) {
                                // Log the specific SQL error and the filename
                                update_option('golf_migration_last_error', "SQL Error in " . basename($file_path) . ": " . $wpdb->last_error);
                                return; // Stop the migration immediately
                            }
                        }
                    }
                }
            }

            // If we reach here, all files processed successfully
            update_option('golf_plugin_db_version', GOLF_PLUGIN_VERSION);
            delete_option('golf_migration_last_error');
        }
    }
}

// Ignition switch: trigger the migration on every admin page load
add_action('admin_init', 'golf_system_run_migrations');