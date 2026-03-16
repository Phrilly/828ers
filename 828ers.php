<?php
/*
Plugin Name: 828ers Golf Handicap System
Description: Automated WHS Handicap Tracking with Git-Triggered Migrations.
Version:     1.0.30
Author:      Philip Dunne
*/

define('GOLF_PLUGIN_VERSION', '1.0.30');

function golf_system_run_migrations() {
    global $wpdb;
    $installed_ver = get_option('golf_plugin_db_version');

    if ($installed_ver !== GOLF_PLUGIN_VERSION) {
        clearstatcache();
        $sql_dir = plugin_dir_path(__FILE__) . 'sql/';
        $files = glob($sql_dir . '*.sql');

        $audit_log = []; 

        if (empty($files)) {
            $audit_log[] = "CRITICAL FAIL: No files found in directory: " . $sql_dir;
            update_option('golf_migration_audit_log', implode("\n", $audit_log));
            return; 
        }

        sort($files); 
        $audit_log[] = "INIT: Found " . count($files) . " files. Starting processing...";

        foreach ($files as $file_path) {
            $filename = basename($file_path);
            $sql_contents = file_get_contents($file_path);
            
            $audit_log[] = "--- FILE: {$filename} (Size: " . strlen($sql_contents) . " bytes) ---";

            // Clean the client-side junk
            $sql_contents = preg_replace('/DELIMITER\s+\S+\s*/i', '', $sql_contents);
            $sql_contents = preg_replace('/DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*/i', '', $sql_contents);

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
                
                $wpdb->hide_errors(); 
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