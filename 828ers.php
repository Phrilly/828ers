<?php
/*
Plugin Name: 828ers Golf Handicap System
Description: Automated WHS Handicap Tracking with Git-Triggered Migrations.
Version:     1.0.13
Author:      Philip Dunne
*/

// 1. Version definition (Engine only runs if this number changes)
define('GOLF_PLUGIN_VERSION', '1.0.13');

/**
 * 828ers Migration Engine
 * This is the "Manager" function you were asking about.
 */
function golf_system_run_migrations() {
    global $wpdb;

    $installed_ver = get_option('golf_plugin_db_version');

    if ($installed_ver !== GOLF_PLUGIN_VERSION) {
        // Path to the /sql/ sub-folder
        $sql_dir = plugin_dir_path(__FILE__) . 'sql/';
        $files = glob($sql_dir . '*.sql');

        if (!empty($files)) {
            sort($files); 

            foreach ($files as $file_path) {
                if (file_exists($file_path)) {
                    $sql_contents = file_get_contents($file_path);

                    // Strip out DELIMITER and DEFINER (they break PHP migrations)
                    $sql_contents = preg_replace('/DELIMITER\s+\S+\s*/i', '', $sql_contents);
                    $sql_contents = preg_replace('/DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*/i', '', $sql_contents);

                    // Split ONLY by our custom marker
                    $queries = preg_split('/--\s*END_QUERY\s*/i', $sql_contents);

                    foreach ($queries as $query) {
                        $query = trim($query);
                        if (!empty($query)) {
                            $result = $wpdb->query($query);
                            
                            if ($result === false) {
                                // If a query fails, we log it and STOP
                                update_option('golf_migration_last_error', "Error in " . basename($file_path) . ": " . $wpdb->last_error);
                                return; 
                            }
                        }
                    }
                }
            }
        }

        // Only update version if the loop finished successfully
        update_option('golf_plugin_db_version', GOLF_PLUGIN_VERSION);
        delete_option('golf_migration_last_error');
    }
}

// 2. This is the "Ignition Switch" that triggers the function above
add_action('admin_init', 'golf_system_run_migrations');