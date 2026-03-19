<?php
add_shortcode('golf_stats_dashboard', function () {
    global $wpdb;

    $selected_year = isset($_GET['stats_year']) ? (int) $_GET['stats_year'] : (int) date('Y');

    $players_table = $wpdb->prefix . 'golf_players';

    $players = $wpdb->get_results("SELECT name FROM {$players_table} ORDER BY player_id ASC", ARRAY_A);

    $h_idx = array_column(
        $wpdb->get_results("SELECT * FROM view_handicap_index", ARRAY_A),
        null,
        'player_name'
    );

    $h_play = array_column(
        $wpdb->get_results("SELECT * FROM view_playing_handicaps", ARRAY_A),
        null,
        'player_name'
    );

    $y_query = $wpdb->prepare("SELECT * FROM view_golf_yearly_stats WHERE stat_year = %d", $selected_year);
    $y_data  = array_column($wpdb->get_results($y_query, ARRAY_A), null, 'player_name');

    $rolling_data = array_column(
        $wpdb->get_results("SELECT * FROM view_golf_rolling_averages", ARRAY_A),
        null,
        'player_name'
    );

    $r_data = array_column(
        $wpdb->get_results("SELECT * FROM view_golf_player_records", ARRAY_A),
        null,
        'player_name'
    );

    $fmt_course_hcp = function ($exact) {
        $exact = (float) ($exact ?? 0);
        if (!$exact) {
            return '-';
        }
        $rounded = (int) round($exact);
        $two_dp  = number_format($exact, 2);
        return $rounded . ' <em style="font-size: calc(100% - 1pt); font-style: italic;">(' . $two_dp . ')</em>';
    };

    ob_start();
    ?>
    <div id="golf-dashboard" class="golf-dashboard-wrapper">
        <div class="stats-filter-bar">
            <form method="get" action="#golf-dashboard">
                <label style="font-weight:bold; margin-right:5px;">Analysis Year:</label>
                <select name="stats_year">
                    <?php for ($y = (int) date('Y'); $y >= 2021; $y--): ?>
                        <option value="<?php echo (int) $y; ?>" <?php selected($selected_year, $y); ?>>
                            <?php echo (int) $y; ?>
                        </option>
                    <?php endfor; ?>
                </select>
                <button type="submit" style="padding: 5px 15px; background: #0073aa; color: #fff; border: none; border-radius: 3px; cursor: pointer; margin-left: 10px;">
                    Update View
                </button>
            </form>
        </div>

        <div class="golf-stats-grid">
            <?php foreach ($players as $p): ?>
                <?php
                $n     = $p['name'];
                $hi    = $h_idx[$n] ?? [];
                $hp    = $h_play[$n] ?? [];
                $yrow  = $y_data[$n] ?? [];
                $avg   = $rolling_data[$n] ?? [];
                $r     = $r_data[$n] ?? [];
                $total = (int) ($yrow['total_rounds'] ?? 0);

                $pct = function ($v) use ($total) {
                    $v = (int) ($v ?? 0);
                    return ($total > 0) ? (round(($v / $total) * 100) . "%") : "0%";
                };

                $current_hi  = number_format((float) ($hi['current_handicap_index'] ?? 0.0), 1);
                $hi_direction = $hi['hi_direction'] ?? 'same';

                if ($hi_direction === 'up') {
                    $hi_class = 'hi-up';
                    $hi_label = 'HI increased recently';
                } elseif ($hi_direction === 'down') {
                    $hi_class = 'hi-down';
                    $hi_label = 'HI decreased recently';
                } else {
                    $hi_class = 'hi-same';
                    $hi_label = 'HI unchanged';
                }
                ?>
                <div class="golf-card">
                    <div class="card-header">
                        <span><?php echo esc_html($n); ?></span>
                        <span class="p-idx-wrap">
                            <span class="p-idx"><?php echo esc_html($current_hi); ?></span>
                            <span class="hi-indicator <?php echo esc_attr($hi_class); ?>"
                                  aria-label="<?php echo esc_attr($hi_label); ?>"
                                  title="<?php echo esc_attr($hi_label); ?>"></span>
                        </span>
                    </div>

                    <div class="sect-hcap">
                        <div class="sect-title">Handicaps</div>
                        <table class="stats-table">
                            <tr style="border-bottom: 1px solid #ddd;">
                                <th style="text-align:left; font-size:11px; color:#666;">Tee</th>
                                <th style="text-align:right; font-size:11px; color:#666;">Course</th>
                                <th style="text-align:right; font-size:11px; color:#666;">Playing</th>
                            </tr>
                            <tr>
                                <td>White</td>
                                <td class="tr"><?php echo wp_kses_post($fmt_course_hcp($hp['white_exact'] ?? 0)); ?></td>
                                <td class="tr"><strong><?php echo (int) ($hp['white_play'] ?? 0); ?></strong></td>
                            </tr>
                            <tr>
                                <td>Yellow</td>
                                <td class="tr"><?php echo wp_kses_post($fmt_course_hcp($hp['yellow_exact'] ?? 0)); ?></td>
                                <td class="tr"><strong><?php echo (int) ($hp['yellow_play'] ?? 0); ?></strong></td>
                            </tr>
                            <tr>
                                <td>Black</td>
                                <td class="tr"><?php echo wp_kses_post($fmt_course_hcp($hp['black_exact'] ?? 0)); ?></td>
                                <td class="tr"><strong><?php echo (int) ($hp['black_play'] ?? 0); ?></strong></td>
                            </tr>
                        </table>
                    </div>

                    <div class="sect-averages">
                        <div class="sect-title">Last 20 Rounds</div>
                        <div style="display:flex; justify-content:space-between; font-size:13px;">
                            <span>Avg Putts: <strong><?php echo esc_html($avg['avg_putts_20'] ?? '-'); ?></strong></span>
                            <span>Avg GIR: <strong><?php echo esc_html($avg['avg_gir_20'] ?? '-'); ?></strong></span>
                        </div>
                    </div>

                    <div class="sect-stats">
                        <div class="sect-title">Stats <?php echo (int) $selected_year; ?></div>
                        <table class="stats-table">
                            <tr><td>Rounds</td><td></td><td class="tr"><strong><?php echo (int) $total; ?></strong></td></tr>
                            <tr><td>Avg Gross</td><td></td><td class="tr"><strong><?php echo esc_html($yrow['avg_gross_year'] ?? '-'); ?></strong></td></tr>
                            <tr><td>Avg Putts</td><td></td><td class="tr"><strong><?php echo esc_html($yrow['avg_putts_year'] ?? '-'); ?></strong></td></tr>
                            <tr><td>Avg GIR</td><td></td><td class="tr"><strong><?php echo esc_html($yrow['avg_gir_year'] ?? '-'); ?></strong></td></tr>
                            <tr>
                                <td>Wins (Nett)</td>
                                <td class="txt-pct"><?php echo isset($yrow['win_pct']) ? esc_html($yrow['win_pct'] . '%') : '0.0%'; ?></td>
                                <td class="tr"><strong><?php echo (int) ($yrow['wins'] ?? 0); ?></strong></td>
                            </tr>
                            <tr><td>&lt; 80</td><td class="txt-pct"><?php echo esc_html($pct($yrow['sub_80'] ?? 0)); ?></td><td class="tr"><?php echo (int) ($yrow['sub_80'] ?? 0); ?></td></tr>
                            <tr><td>80-84</td><td class="txt-pct"><?php echo esc_html($pct($yrow['cat_80_84'] ?? 0)); ?></td><td class="tr"><?php echo (int) ($yrow['cat_80_84'] ?? 0); ?></td></tr>
                            <tr><td>85-89</td><td class="txt-pct"><?php echo esc_html($pct($yrow['cat_85_89'] ?? 0)); ?></td><td class="tr"><?php echo (int) ($yrow['cat_85_89'] ?? 0); ?></td></tr>
                            <tr><td>90-99</td><td class="txt-pct"><?php echo esc_html($pct($yrow['cat_90_99'] ?? 0)); ?></td><td class="tr"><?php echo (int) ($yrow['cat_90_99'] ?? 0); ?></td></tr>
                            <tr><td>100+</td><td class="txt-pct"><?php echo esc_html($pct($yrow['cat_100_plus'] ?? 0)); ?></td><td class="tr"><?php echo (int) ($yrow['cat_100_plus'] ?? 0); ?></td></tr>
                        </table>
                    </div>

                    <div class="sect-recs">
                        <div class="sect-title">Records</div>
                        <div style="font-size:13px; margin-bottom:5px;">
                            Best: <strong><?php echo esc_html($r['best_score'] ?? '-'); ?></strong>
                            <span class="rec-sub">
                                <?php echo !empty($r['best_date']) ? esc_html('on ' . date('j M y', strtotime($r['best_date']))) : ''; ?>
                            </span>
                        </div>
                        <div style="font-size:13px;">
                            Streak: <strong><?php echo (int) ($r['streak_count'] ?? 0); ?></strong>
                            <span class="rec-sub">
                                <?php
                                if (!empty($r['streak_start']) && !empty($r['streak_end'])) {
                                    echo esc_html(date('j M y', strtotime($r['streak_start'])) . ' — ' . date('j M y', strtotime($r['streak_end'])));
                                }
                                ?>
                            </span>
                        </div>
                    </div>

                </div>
            <?php endforeach; ?>
        </div>
    </div>
    <?php

    return ob_get_clean();
});