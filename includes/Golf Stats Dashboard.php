<?php
add_shortcode('golf_stats_dashboard', function () {
    global $wpdb;

    $year = isset($_GET['stats_year']) ? (int) $_GET['stats_year'] : (int) date('Y');
    $players_table = $wpdb->prefix . 'golf_players';

    $players = $wpdb->get_results("SELECT name FROM {$players_table} ORDER BY player_id ASC", ARRAY_A);

    $by_name = function ($sql) use ($wpdb) {
        return array_column($wpdb->get_results($sql, ARRAY_A), null, 'player_name');
    };

    $h_idx   = $by_name("SELECT * FROM view_handicap_index");
    $h_play  = $by_name("SELECT * FROM view_playing_handicaps");
    $rolling = $by_name("SELECT * FROM view_golf_rolling_averages");
    $records = $by_name("SELECT * FROM view_golf_player_records");

    $yearly = array_column(
        $wpdb->get_results(
            $wpdb->prepare("SELECT * FROM view_golf_yearly_stats WHERE stat_year = %d", $year),
            ARRAY_A
        ),
        null,
        'player_name'
    );

    $fmt = function ($v, $d = 1) {
        return ($v === null || $v === '') ? '-' : (is_numeric($v) ? number_format((float) $v, $d) : $v);
    };

    $pct = function ($v, $total) {
        $v = (int) ($v ?? 0);
        return $total > 0 ? round(($v / $total) * 100) . '%' : '0%';
    };

    $course = function ($exact) {
        $exact = (float) ($exact ?? 0);
        if (!$exact) return '-';
        return round($exact) . ' <span class="hcp-exact">(' . number_format($exact, 2) . ')</span>';
    };

    ob_start(); ?>
    <div id="golf-dashboard" class="golf-dashboard">
        <div class="filter-bar">
            <form method="get" action="#golf-dashboard" class="filter-form">
                <label for="stats_year">Analysis Year</label>
                <select name="stats_year" id="stats_year">
                    <?php for ($y = (int) date('Y'); $y >= 2021; $y--) : ?>
                        <option value="<?php echo $y; ?>" <?php selected($year, $y); ?>><?php echo $y; ?></option>
                    <?php endfor; ?>
                </select>
                <button type="submit">Update View</button>
            </form>
        </div>

        <div class="golf-stats-grid">
            <?php foreach ($players as $player) :
                $name  = $player['name'];
                $hi    = $h_idx[$name]   ?? [];
                $hp    = $h_play[$name]  ?? [];
                $avg   = $rolling[$name] ?? [];
                $rec   = $records[$name] ?? [];
                $yr    = $yearly[$name]  ?? [];
                $total = (int) ($yr['total_rounds'] ?? 0);

                $dir = $hi['hi_direction'] ?? 'same';
                $dir_class = $dir === 'up' ? 'up' : ($dir === 'down' ? 'down' : 'same');
                $dir_label = $dir === 'up' ? 'HI increased recently' : ($dir === 'down' ? 'HI decreased recently' : 'HI unchanged');

                $score_rows = [
                    ['Rounds', '', (int) $total],
                    ['Avg Gross', '', $fmt($yr['avg_gross_year'] ?? null)],
                    ['Avg Putts', '', $fmt($yr['avg_putts_year'] ?? null)],
                    ['Avg GIR', '', $fmt($yr['avg_gir_year'] ?? null)],
                    ['Wins (Nett)', isset($yr['win_pct']) ? $fmt($yr['win_pct'], 1) . '%' : '0.0%', (int) ($yr['wins'] ?? 0)],
                    ['< 80', $pct($yr['sub_80'] ?? 0, $total), (int) ($yr['sub_80'] ?? 0)],
                    ['80-84', $pct($yr['cat_80_84'] ?? 0, $total), (int) ($yr['cat_80_84'] ?? 0)],
                    ['85-89', $pct($yr['cat_85_89'] ?? 0, $total), (int) ($yr['cat_85_89'] ?? 0)],
                    ['90-99', $pct($yr['cat_90_99'] ?? 0, $total), (int) ($yr['cat_90_99'] ?? 0)],
                    ['100+', $pct($yr['cat_100_plus'] ?? 0, $total), (int) ($yr['cat_100_plus'] ?? 0)],
                ];
            ?>
                <article class="golf-card">
                    <header class="card-header">
                        <h3 class="player-name"><?php echo esc_html($name); ?></h3>
                        <div class="player-hi">
                            <span class="hi-value"><?php echo esc_html(number_format((float) ($hi['current_handicap_index'] ?? 0), 1)); ?></span>
                            <span class="hi-indicator <?php echo esc_attr($dir_class); ?>" title="<?php echo esc_attr($dir_label); ?>" aria-label="<?php echo esc_attr($dir_label); ?>"></span>
                        </div>
                    </header>

                    <section class="card-section alt">
                        <h4 class="section-title">Handicaps</h4>
                        <table class="stats-table handicaps">
                            <thead>
                                <tr><th>Tee</th><th class="right">Course</th><th class="right">Playing</th></tr>
                            </thead>
                            <tbody>
                                <tr><td>White</td><td class="right"><?php echo wp_kses($course($hp['white_exact'] ?? 0), ['span' => ['class' => true]]); ?></td><td class="right"><strong><?php echo (int) ($hp['white_play'] ?? 0); ?></strong></td></tr>
                                <tr><td>Yellow</td><td class="right"><?php echo wp_kses($course($hp['yellow_exact'] ?? 0), ['span' => ['class' => true]]); ?></td><td class="right"><strong><?php echo (int) ($hp['yellow_play'] ?? 0); ?></strong></td></tr>
                                <tr><td>Black</td><td class="right"><?php echo wp_kses($course($hp['black_exact'] ?? 0), ['span' => ['class' => true]]); ?></td><td class="right"><strong><?php echo (int) ($hp['black_play'] ?? 0); ?></strong></td></tr>
                            </tbody>
                        </table>
                    </section>

                    <section class="card-section soft">
                        <h4 class="section-title">Last 20 Rounds</h4>
                        <table class="stats-table">
                            <tbody>
                                <tr><td>Avg Putts</td><td></td><td class="right"><strong><?php echo esc_html($fmt($avg['avg_putts_20'] ?? null)); ?></strong></td></tr>
                                <tr><td>Avg GIR</td><td></td><td class="right"><strong><?php echo esc_html($fmt($avg['avg_gir_20'] ?? null)); ?></strong></td></tr>
                            </tbody>
                        </table>
                    </section>

                    <section class="card-section grow">
                        <h4 class="section-title">Stats <?php echo $year; ?></h4>
                        <table class="stats-table">
                            <tbody>
                                <?php foreach ($score_rows as $row) : ?>
                                    <tr>
                                        <td><?php echo esc_html($row[0]); ?></td>
                                        <td class="pct"><?php echo esc_html($row[1]); ?></td>
                                        <td class="right"><?php echo is_numeric($row[2]) ? $row[2] : esc_html($row[2]); ?></td>
                                    </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </section>

                    <section class="card-section">
                        <h4 class="section-title">Records</h4>
                        <table class="stats-table">
                            <tbody>
                                <tr><td>Best</td><td></td><td class="right"><strong><?php echo esc_html($rec['best_score'] ?? '-'); ?></strong></td></tr>
                                <tr><td colspan="3" class="subrow"><?php echo !empty($rec['best_date']) ? esc_html('on ' . date('j M y', strtotime($rec['best_date']))) : ''; ?></td></tr>
                                <tr><td>Streak</td><td></td><td class="right"><strong><?php echo (int) ($rec['streak_count'] ?? 0); ?></strong></td></tr>
                                <tr><td colspan="3" class="subrow"><?php
                                    if (!empty($rec['streak_start']) && !empty($rec['streak_end'])) {
                                        echo esc_html(date('j M y', strtotime($rec['streak_start'])) . ' — ' . date('j M y', strtotime($rec['streak_end'])));
                                    }
                                ?></td></tr>
                            </tbody>
                        </table>
                    </section>
                </article>
            <?php endforeach; ?>
        </div>
    </div>
    <?php
    return ob_get_clean();
});
