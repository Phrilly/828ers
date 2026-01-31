/* ======================================================
   HANDICAP INDEX CHART — 4 Players (Last 12 Months)
   Shortcode: [golf_hcp_chart]
   - Smooth continuous lines (gaps filled with previous index)
   - Production-ready with error handling
   ====================================================== */
add_shortcode('golf_hcp_chart', function() {
    global $wpdb;

    $history_table = $wpdb->prefix . 'golf_handicap_history';
    $players_table = $wpdb->prefix . 'golf_players';

    // UPDATE THESE: your actual 4 player_ids
    $player_ids = [1, 2, 3, 4];  // ← REPLACE with real player_id values
    $player_list = implode(',', $player_ids);

    // Get handicap history for last 12 months
    $rows = $wpdb->get_results("
        SELECT 
            h.date_played,
            p.name as player_name,
            h.hcp_after as handicap_index
        FROM {$history_table} h
        JOIN {$players_table} p ON p.player_id = h.player_id
        WHERE h.date_played >= (CURDATE() - INTERVAL 1 YEAR)
          AND h.player_id IN ({$player_list})
        ORDER BY h.date_played ASC, p.name ASC
    ");

    if (empty($rows)) {
        return '<div class="golf-chart-no-data" style="text-align:center; padding:40px; color:#666;">
                  <p>No handicap history data found for the last 12 months.</p>
                </div>';
    }

    // Build data structure: date -> [player_name => index]
    $data_by_date = [];
    $players = [];
    foreach ($rows as $row) {
        $data_by_date[$row->date_played][$row->player_name] = (float)$row->handicap_index;
        $players[$row->player_name] = true;
    }

    // FILL GAPS WITH PREVIOUS INDEX (creates continuous lines)
    ksort($data_by_date);
    $dates = array_keys($data_by_date);
    foreach ($dates as $i => $date) {
        foreach (array_keys($players) as $player) {
            if (!isset($data_by_date[$date][$player])) {
                // Find last known value for this player
                for ($j = $i - 1; $j >= 0; $j--) {
                    $prev_date = $dates[$j];
                    if (isset($data_by_date[$prev_date][$player])) {
                        $data_by_date[$date][$player] = $data_by_date[$prev_date][$player];
                        break;
                    }
                }
            }
        }
    }

    // Build Google Charts row format
    $chart_data = [];
    foreach ($data_by_date as $date => $indices) {
        $row = [$date];
        foreach (array_keys($players) as $player) {
            $row[] = $indices[$player] ?? null;
        }
        $chart_data[] = $row;
    }

    ob_start(); ?>
    <div class="golf-hcp-chart-wrapper" style="margin: 30px 0; max-width: 1000px; margin-left: auto; margin-right: auto;">
        <h3 style="text-align: center; margin-bottom: 20px; color: #333; font-size: 22px;">Handicap Index — Last 12 Months</h3>
        <div id="hcp-chart" style="width: 100%; height: 450px; border: 1px solid #ddd; border-radius: 8px;"></div>
    </div>

    <script src="https://www.gstatic.com/charts/loader.js" async defer></script>
    <script type="text/javascript">
        (function() {
            window.addEventListener('load', function() {
                if (typeof google === 'undefined') {
                    document.getElementById('hcp-chart').innerHTML = 
                        '<p style="color:#d63638; text-align:center; padding:20px;">Chart unavailable (Google Charts blocked)</p>';
                    return;
                }

                google.charts.load('current', {'packages':['corechart']});
                google.charts.setOnLoadCallback(drawChart);
            });

            function drawChart() {
                const rawData = <?php echo json_encode($chart_data); ?>;

                if (rawData.length === 0) {
                    document.getElementById('hcp-chart').innerHTML = 
                        '<p style="color:#ff8c00; text-align:center; padding:20px;">No data points to chart</p>';
                    return;
                }

                const data = new google.visualization.DataTable();
                data.addColumn('date', 'Date');
                <?php foreach (array_keys($players) as $player): ?>
                data.addColumn('number', '<?php echo esc_js($player); ?>');
                <?php endforeach; ?>

                const parsed = rawData.map(row => {
                    row[0] = new Date(row[0] + 'T00:00:00');
                    return row.map((val, idx) => idx === 0 ? val : (val || null));
                });
                data.addRows(parsed);

                const options = {
                    title: '',
                    legend: {position: 'bottom', textStyle: {fontSize: 12}},
                    curveType: 'function',           // Smooth curves
                    interpolation: 'line',            // Connect all points
                    hAxis: {
                        title: 'Date',
                        titleTextStyle: {italic: false},
                        slantedText: false,
                        textStyle: {fontSize: 11}
                    },
                    vAxis: {
                        title: 'Handicap Index',
                        titleTextStyle: {italic: false},
                        reverseDirection: true,         // Lower index higher up
                        gridlines: {count: 5},
                        textStyle: {fontSize: 11}
                    },
                    chartArea: {left: 70, top: 30, width: '78%', height: '65%'},
                    colors: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'],  // Blue, Orange, Green, Red
                    lineWidth: 3,                       // Thicker lines
                    pointSize: 1,                       // Visible data points
                    backgroundColor: {fill: 'transparent'},
                    series: {
                        0: {lineWidth: 3},  // Phil
                        1: {lineWidth: 3},  // Player 2
                        2: {lineWidth: 3},  // Player 3  
                        3: {lineWidth: 3}   // Player 4
                    }
                };

                const chart = new google.visualization.LineChart(
                    document.getElementById('hcp-chart')
                );
                chart.draw(data, options);

                // Responsive resize
                window.addEventListener('resize', function() {
                    chart.draw(data, options);
                });
            }
        })();
    </script>
    <?php
    return ob_get_clean();
});
