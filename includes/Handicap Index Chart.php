<?php
add_shortcode('golf_hcp_chart', function() {
    global $wpdb;


    $history_table = $wpdb->prefix . 'golf_handicap_history';
    $players_table = $wpdb->prefix . 'golf_players';


    $player_ids = [1, 2, 3, 4];
    $player_list = implode(',', $player_ids);


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


    $data_by_date = [];
    $players = [];
    foreach ($rows as $row) {
        $data_by_date[$row->date_played][$row->player_name] = (float) $row->handicap_index;
        $players[$row->player_name] = true;
    }


    ksort($data_by_date);
    $dates = array_keys($data_by_date);


    foreach ($dates as $i => $date) {
        foreach (array_keys($players) as $player) {
            if (!isset($data_by_date[$date][$player])) {
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


    $chart_data = [];
    foreach ($data_by_date as $date => $indices) {
        $r = [$date];
        foreach (array_keys($players) as $player) {
            $r[] = $indices[$player] ?? null;
        }
        $chart_data[] = $r;
    }


    $diff_players = array_values(array_filter(array_keys($players), function($player) {
        return $player !== 'Phil B';
    }));


    $diff_chart_data = [];
    foreach ($data_by_date as $date => $indices) {
        $phil_b = $indices['Phil B'] ?? null;
        $r = [$date];
        foreach ($diff_players as $player) {
            $r[] = ($phil_b !== null && isset($indices[$player])) ? round($indices[$player] - $phil_b, 1) : null;
        }
        $diff_chart_data[] = $r;
    }


    $players_keys = array_keys($players);
    $chart_json = wp_json_encode($chart_data);
    $diff_chart_json = wp_json_encode($diff_chart_data);


    ob_start();
    ?>
    <div class="golf-hcp-chart-wrapper" style="margin: 30px 0; max-width: 1000px; margin-left: auto; margin-right: auto;">
        <h3 style="text-align: center; margin-bottom: 20px; color: #333; font-size: 22px;">Handicap Index — Last 12 Months</h3>
        <div id="hcp-chart" style="width: 100%; height: 450px; border: 1px solid #ddd; border-radius: 8px;"></div>
    </div>

    <div class="golf-hcp-chart-wrapper" style="margin: 30px 0; max-width: 1000px; margin-left: auto; margin-right: auto;">
        <h3 style="text-align: center; margin-bottom: 20px; color: #333; font-size: 22px;">HI Difference vs Phil B — Last 12 Months</h3>
        <div id="hcp-diff-chart" style="width: 100%; height: 450px; border: 1px solid #ddd; border-radius: 8px;"></div>
    </div>


    <script src="https://www.gstatic.com/charts/loader.js" async defer></script>
    <script type="text/javascript">
    (function() {
        window.addEventListener('load', function() {
            if (typeof google === 'undefined') {
                document.getElementById('hcp-chart').innerHTML =
                    '<p style="color:#d63638; text-align:center; padding:20px;">Chart unavailable (Google Charts blocked)</p>';
                document.getElementById('hcp-diff-chart').innerHTML =
                    '<p style="color:#d63638; text-align:center; padding:20px;">Chart unavailable (Google Charts blocked)</p>';
                return;
            }


            google.charts.load('current', {'packages':['corechart']});
            google.charts.setOnLoadCallback(drawChart);
        });


        function drawChart() {
            const rawData = <?php echo $chart_json; ?>;
            const diffRawData = <?php echo $diff_chart_json; ?>;


            if (!rawData || rawData.length === 0) {
                document.getElementById('hcp-chart').innerHTML =
                    '<p style="color:#ff8c00; text-align:center; padding:20px;">No data points to chart</p>';
                document.getElementById('hcp-diff-chart').innerHTML =
                    '<p style="color:#ff8c00; text-align:center; padding:20px;">No data points to chart</p>';
                return;
            }


            const data = new google.visualization.DataTable();
            data.addColumn('date', 'Date');


            <?php foreach ($players_keys as $player): ?>
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
                curveType: 'function',
                hAxis: {
                    title: 'Date',
                    titleTextStyle: {italic: false},
                    slantedText: false,
                    textStyle: {fontSize: 11}
                },
                vAxis: {
                    title: 'Handicap Index',
                    titleTextStyle: {italic: false},
                    reverseDirection: true,
                    gridlines: {count: 5},
                    textStyle: {fontSize: 11}
                },
                chartArea: {left: 70, top: 30, width: '78%', height: '65%'},
                colors: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'],
                lineWidth: 3,
                pointSize: 1
            };


            const chart = new google.visualization.LineChart(document.getElementById('hcp-chart'));
            chart.draw(data, options);


            const diffData = new google.visualization.DataTable();
            diffData.addColumn('date', 'Date');

            <?php foreach ($diff_players as $player): ?>
                diffData.addColumn('number', '<?php echo esc_js($player); ?>');
            <?php endforeach; ?>

            const parsedDiff = diffRawData.map(row => {
                row[0] = new Date(row[0] + 'T00:00:00');
                return row.map((val, idx) => idx === 0 ? val : (val || null));
            });
            diffData.addRows(parsedDiff);


            const diffOptions = {
                title: '',
                legend: {position: 'bottom', textStyle: {fontSize: 12}},
                curveType: 'function',
                hAxis: {
                    title: 'Date',
                    titleTextStyle: {italic: false},
                    slantedText: false,
                    textStyle: {fontSize: 11}
                },
                vAxis: {
                    title: 'HI vs Phil B',
                    titleTextStyle: {italic: false},
                    gridlines: {count: 5},
                    textStyle: {fontSize: 11}
                },
                chartArea: {left: 70, top: 30, width: '78%', height: '65%'},
                colors: ['#1f77b4', '#2ca02c', '#d62728'],
                lineWidth: 3,
                pointSize: 1
            };


            const diffChart = new google.visualization.LineChart(document.getElementById('hcp-diff-chart'));
            diffChart.draw(diffData, diffOptions);


            window.addEventListener('resize', function() {
                chart.draw(data, options);
                diffChart.draw(diffData, diffOptions);
            });
        }
    })();
    </script>
    <?php


    return ob_get_clean();
});