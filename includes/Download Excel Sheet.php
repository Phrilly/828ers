/**
 * GOLF DATA EXPORT ENGINE
 * Action: admin_post_export_golf_data
 */

// 1. Hook the export function to WordPress admin-post
add_action('admin_post_export_golf_data', 'golf_export_engine_v1');

function golf_export_engine_v1() {
    // Basic security check
    if (!current_user_can('edit_posts')) wp_die('Unauthorized');
    
    global $wpdb;

    // Fetch all records from your standardized history view
    $results = $wpdb->get_results("SELECT * FROM wp_golf_dashboard_history ORDER BY date_played DESC", ARRAY_A);

    if (empty($results)) wp_die('No data found to export.');

    // Set headers to force the browser to download a CSV file
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename=golf_master_export_'.date('Y-m-d').'.csv');

    $output = fopen('php://output', 'w');

    // Create Column Headers (Matches your desktop history columns)
    fputcsv($output, array('Date', 'Player', 'Tee', 'Gross', 'Nett', 'Diff', 'Putts', 'GIR'));

    // Fill the CSV with database rows
    foreach ($results as $row) {
        fputcsv($output, array(
            $row['date_played'],
            $row['player_name'],
            $row['tee_colour'],
            $row['gross_score'],
            $row['net_score'],
            $row['differential'],
            $row['putts'],
            $row['gir']
        ));
    }
    
    fclose($output);
    exit;
}