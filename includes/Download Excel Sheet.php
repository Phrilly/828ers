<?php
/**
 * GOLF DATA EXPORT ENGINE
 * Action: admin_post_export_golf_data
 */

add_action('admin_post_export_golf_data', 'golf_export_engine_v1');

function golf_export_engine_v1() {
    if (!current_user_can('edit_posts')) wp_die('Unauthorized');

    global $wpdb;

    // Use $wpdb->prefix — never hardcode 'wp_'
    $history_view = 'view_golf_dashboard_history';
    $results = $wpdb->get_results("SELECT * FROM {$history_view} ORDER BY date_played DESC", ARRAY_A);

    if (empty($results)) wp_die('No data found to export.');

    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename=golf_master_export_' . date('Y-m-d') . '.csv');

    $output = fopen('php://output', 'w');

    fputcsv($output, ['Date', 'Player', 'Tee', 'Gross', 'Nett', 'Diff', 'Putts', 'GIR']);

    foreach ($results as $row) {
        fputcsv($output, [
            $row['date_played'],
            $row['player_name'],
            $row['tee_colour'],
            $row['gross_score'],
            $row['net_score'],
            $row['differential'],
            $row['putts'],
            $row['gir'],
        ]);
    }

    fclose($output);
    exit;
}
