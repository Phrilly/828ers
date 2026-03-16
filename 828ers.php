function golf_system_run_migrations() {
    global $wpdb;
    $installed_ver = get_option('golf_plugin_db_version');

    if ($installed_ver === GOLF_PLUGIN_VERSION) return;

    $sql_dir = plugin_dir_path(__FILE__) . 'sql/';
    $files = glob($sql_dir . '*.sql');

    if (!empty($files)) {
        sort($files); 
        foreach ($files as $file_path) {
            $sql_contents = file_get_contents($file_path);

            // 1. STRIP CLIENT-SIDE JUNK
            // We must remove these because MariaDB will reject them via PHP
            $sql_contents = preg_replace('/DELIMITER\s+\S+\s*/i', '', $sql_contents);
            $sql_contents = preg_replace('/DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*/i', '', $sql_contents);

            // 2. THE SHIELD SPLIT
            // We split ONLY at our custom marker. This keeps the BEGIN...END block whole.
            $queries = preg_split('/--\s*END_QUERY\s*/i', $sql_contents);

            foreach ($queries as $query) {
                $query = trim($query);
                if (empty($query)) continue;

                // 3. EXECUTION WITH ERROR CATCHING
                $result = $wpdb->query($query);
                
                if ($result === false) {
                    // LOG THE ERROR TO THE DATABASE so you can see it in DBeaver
                    update_option('golf_migration_last_error', "Error in " . basename($file_path) . ": " . $wpdb->last_error);
                    return; // HALT EVERYTHING. Do not update version.
                }
            }
        }
    }
    // Only happens if every single query in every file succeeded
    update_option('golf_plugin_db_version', GOLF_PLUGIN_VERSION);
    delete_option('golf_migration_last_error');
}