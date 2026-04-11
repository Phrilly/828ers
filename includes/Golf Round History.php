<?php
/**
 * Golf Round History
 * Shortcode: [golf_round_history]
 * AJAX action: gh_load_history
 */

add_shortcode('golf_round_history', function () {
    global $wpdb;

    $players_table = $wpdb->prefix . 'golf_players';

    $player_list = $wpdb->get_results("SELECT player_id, name FROM {$players_table} ORDER BY name ASC");

    $nonce = wp_create_nonce('gh_ajax_nonce');

    ob_start();
    ?>
    <div id="golf-history-app" data-page="1" data-player="0">
        <div class="history-filter-bar">
            <label>Filter Player:</label>
            <select id="gh-filter">
                <option value="0">-- All Players --</option>
                <?php if ($player_list): ?>
                    <?php foreach ($player_list as $p): ?>
                        <option value="<?php echo (int) $p->player_id; ?>">
                            <?php echo esc_html($p->name); ?>
                        </option>
                    <?php endforeach; ?>
                <?php endif; ?>
            </select>
        </div>

        <div id="gh-range" class="history-range" style="margin: 10px 0; font-style: italic;"></div>

        <div class="history-scroll" id="gh-table-wrap" style="min-height: 200px; position: relative;">
            <p id="gh-loading">Loading stats...</p>
        </div>

        <div class="history-pagination" id="gh-pagination"></div>
    </div>

    <script>
    (function () {
        const app    = document.getElementById('golf-history-app');
        const table  = document.getElementById('gh-table-wrap');
        const pager  = document.getElementById('gh-pagination');
        const range  = document.getElementById('gh-range');
        const filter = document.getElementById('gh-filter');

        function load(page = 1, player = 0) {
            table.style.opacity = '0.5';
            app.dataset.page = page;
            app.dataset.player = player;

            fetch('<?php echo esc_url(admin_url('admin-ajax.php')); ?>', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({
                    action: 'gh_load_history',
                    page: page,
                    player: player,
                    gh_nonce: '<?php echo esc_js($nonce); ?>'
                })
            })
            .then(r => r.json())
            .then(d => {
                table.innerHTML = d.table || '';
                pager.innerHTML = d.pagination || '';
                range.innerHTML = d.range || '';
                table.style.opacity = '1';

                if (page > 1) {
                    app.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            })
            .catch(() => {
                table.innerHTML = '<p>Failed to load.</p>';
                table.style.opacity = '1';
            });
        }

        pager.addEventListener('click', (e) => {
            const target = e.target.closest('[data-page]');
            if (!target) return;
            e.preventDefault();
            load(parseInt(target.dataset.page, 10), filter.value);
        });

        filter.addEventListener('change', () => {
            load(1, filter.value);
        });

        // Hole-by-Hole Accordion Listener
        table.addEventListener('click', (e) => {
            const row = e.target.closest('.clickable-row');
            if (!row) return;

            const scoreId = row.dataset.scoreId;
            const nextRow = row.nextElementSibling;

            // If it's already open, close it
            if (nextRow && nextRow.classList.contains('hbh-dropdown')) {
                nextRow.remove();
                return;
            }

            // Close any other open dropdowns
            document.querySelectorAll('.hbh-dropdown').forEach(el => el.remove());

            // Create the drop out row
            const dropRow = document.createElement('tr');
            dropRow.className = 'hbh-dropdown';
            dropRow.innerHTML = `<td colspan="12" style="padding:0; background:#fafafa; border-bottom: 2px solid #ddd;"><div style="padding:30px; text-align:center; color:#666;">Loading Scorecard...</div></td>`;
            row.after(dropRow);

            // Fetch the scorecard data
            const formData = new URLSearchParams();
            formData.append('action', 'gh_load_scorecard');
            formData.append('score_id', scoreId);
            formData.append('gh_nonce', '<?php echo esc_js($nonce); ?>');

            fetch('<?php echo esc_url(admin_url('admin-ajax.php')); ?>', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(d => {
                if(d.success) {
                    dropRow.querySelector('td').innerHTML = d.data;
                } else {
                    dropRow.querySelector('td').innerHTML = `<div style="padding:20px; color:#d63638; text-align:center;">${d.data || 'Scorecard data not yet synced from England Golf.'}</div>`;
                }
            })
            .catch(() => dropRow.remove());
        });

        load();
    })();
    </script>
    <?php
    return ob_get_clean();
});

add_action('wp_ajax_gh_load_history', 'gh_load_history');
add_action('wp_ajax_nopriv_gh_load_history', 'gh_load_history');

function gh_load_history() {
    check_ajax_referer('gh_ajax_nonce', 'gh_nonce');
    global $wpdb;

    $limit  = 25;
    $page   = max(1, (int) ($_POST['page'] ?? 1));
    $player = (int) ($_POST['player'] ?? 0);
    $offset = ($page - 1) * $limit;

    $history_view = 'view_golf_dashboard_history';

    $where_sql  = '';
    $where_args = [];
    if ($player) {
        $where_sql = 'WHERE player_id = %d';
        $where_args[] = $player;
    }

    if ($where_sql) {
        $total = (int) $wpdb->get_var(
            $wpdb->prepare("SELECT COUNT(*) FROM {$history_view} {$where_sql}", ...$where_args)
        );
    } else {
        $total = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$history_view}");
    }

    if ($where_sql) {
        $sql = $wpdb->prepare(
            "SELECT * FROM {$history_view} {$where_sql} ORDER BY date_played DESC, score_id DESC LIMIT %d OFFSET %d",
            ...array_merge($where_args, [$limit, $offset])
        );
    } else {
        $sql = $wpdb->prepare(
            "SELECT * FROM {$history_view} ORDER BY date_played DESC, score_id DESC LIMIT %d OFFSET %d",
            $limit,
            $offset
        );
    }

    $rows = $wpdb->get_results($sql, ARRAY_A);

    $total_pages = max(1, (int) ceil($total / $limit));
    $start_row   = $total ? ($offset + 1) : 0;
    $end_row     = min($offset + $limit, $total);

    $show_cutoff_line = ($player > 0 && $page === 1);
    $window_size      = 20;
    $window_seen      = 0;
    $cutoff_drawn     = false;
    $below_cutoff     = false;

    ob_start();
    ?>
    <table class="history-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Player</th>
                <th>Tee</th>
                <th class="tc">Gross</th>
                <th class="tc">HI</th>
                <th class="tc">Nett</th>
                <th class="tc">Diff</th>
                <th class="tc">PCC</th>
                <th class="tc">Low HI</th>
                <th class="tc">Putts</th>
                <th class="tc">GIR</th>
                <th class="tc">Adj</th>
            </tr>
        </thead>
        <tbody>
        <?php if ($rows): ?>
            <?php foreach ($rows as $idx => $r): ?>
                <?php
                $cap = !empty($r['cap_applied']);
                $esr = !empty($r['esr_applied']);

                $row_class = '';
                if ($cap) $row_class .= ' is-cap';
                if ($esr) $row_class .= ' is-esr';
                if (!empty($r['is_excluded'])) $row_class .= ' is-excluded';
                if ($below_cutoff) $row_class .= ' dropped-out';

                $adj = '';
                if ($esr) $adj .= 'E';
                if ($cap) $adj .= 'C';

                $hi = (isset($r['starting_index']) && $r['starting_index'] !== null && $r['starting_index'] !== '')
                    ? number_format((float) $r['starting_index'], 1)
                    : '-';

                $low_hi = (isset($r['low_hi_365']) && $r['low_hi_365'] !== null && $r['low_hi_365'] !== '')
                    ? number_format((float) $r['low_hi_365'], 1)
                    : '-';

                $pcc = (isset($r['pcc']) && $r['pcc'] != 0)
                    ? '<strong style="color: #d9534f;">'.(int)$r['pcc'].'</strong>'
                    : '0';

                $qualifies_for_window =
                    empty($r['is_excluded']) &&
                    isset($r['starting_index']) &&
                    $r['starting_index'] !== null &&
                    $r['starting_index'] !== '';

                $gross_class = !empty($r['is_counting']) ? 'gross-value is-counting' : 'gross-value';
                $gross_title = !empty($r['is_counting']) ? ' title="Counts toward Handicap Index"' : '';

                $player_name    = (string) ($r['player_name'] ?? '');
                $player_initial = trim((string) ($r['player_initials'] ?? ''));
                if ($player_initial === '') {
                    $player_initial = $player_name;
                }
                ?>
                <tr class="<?php echo esc_attr(trim($row_class)); ?> clickable-row" data-score-id="<?php echo (int)($r['score_id'] ?? 0); ?>" style="cursor: pointer;" title="Click to view scorecard">
                    <td><?php echo esc_html(date('d/m/y', strtotime($r['date_played']))); ?></td>
                    <td>
                        <strong class="player-full"><?php echo esc_html($player_name); ?></strong>
                        <strong class="player-initials"><?php echo esc_html($player_initial); ?></strong>
                    </td>
                    <td>
                        <span class="tee-badge tee-<?php echo esc_attr(strtolower($r['tee_colour'] ?? '')); ?>">
                            <?php echo esc_html($r['tee_colour'] ?? ''); ?>
                        </span>
                    </td>

                    <td class="gross-cell">
                        <span class="<?php echo esc_attr($gross_class); ?>"<?php echo $gross_title; ?>>
                            <?php echo (int) ($r['gross_score'] ?? 0); ?>
                        </span>
                    </td>

                    <td class="tc"><?php echo esc_html($hi); ?></td>

                    <td class="tc"><?php echo (int) ($r['net_score'] ?? 0); ?></td>
                    <td class="tc"><?php echo esc_html(number_format((float) ($r['differential'] ?? 0), 1)); ?></td>
                    <td class="tc"><?php echo wp_kses($pcc, ['strong' => ['style' => true]]); ?></td>
                    <td class="tc" style="color: #666; font-style: italic;"><?php echo esc_html($low_hi); ?></td>

                    <td class="tc"><?php echo (int) ($r['putts'] ?? 0); ?></td>
                    <td class="tc"><?php echo (int) ($r['gir'] ?? 0); ?></td>

                    <td class="tc">
                        <?php if ($adj !== ''): ?>
                            <span class="adj-badge"><?php echo esc_html($adj); ?></span>
                        <?php endif; ?>
                    </td>
                </tr>

                <?php
                if (
                    $show_cutoff_line &&
                    !$cutoff_drawn &&
                    $qualifies_for_window
                ) {
                    $window_seen++;

                    if ($window_seen === $window_size && $idx < count($rows) - 1) {
                        $cutoff_drawn = true;
                        $below_cutoff = true;
                        ?>
                        <tr class="history-cutoff">
                            <td colspan="12"></td>
                        </tr>
                        <?php
                    }
                }
                ?>
            <?php endforeach; ?>
        <?php else: ?>
            <tr><td colspan="12">No rounds found.</td></tr>
        <?php endif; ?>
        </tbody>
    </table>
    <?php
    $table_html = ob_get_clean();

    ob_start();

    $window = 2;
    $start  = max(1, $page - $window);
    $end    = min($total_pages, $page + $window);

    if ($page > 1) {
        echo "<a class='page-numbers prev' href='#' data-page='" . ($page - 1) . "'>« Prev</a>";
    }

    if ($start > 1) {
        echo "<a class='page-numbers' href='#' data-page='1'>1</a>";
        if ($start > 2) echo "<span class='page-numbers dots'>…</span>";
    }

    for ($i = $start; $i <= $end; $i++) {
        if ($i === $page) {
            echo "<span class='page-numbers current'>{$i}</span>";
        } else {
            echo "<a class='page-numbers' href='#' data-page='{$i}'>{$i}</a>";
        }
    }

    if ($end < $total_pages) {
        if ($end < $total_pages - 1) echo "<span class='page-numbers dots'>…</span>";
        echo "<a class='page-numbers' href='#' data-page='{$total_pages}'>{$total_pages}</a>";
    }

    if ($page < $total_pages) {
        echo "<a class='page-numbers next' href='#' data-page='" . ($page + 1) . "'>Next »</a>";
    }

    $pagination_html = ob_get_clean();

    wp_send_json([
        'table'      => $table_html,
        'pagination' => $pagination_html,
        'range'      => "Showing {$start_row}–{$end_row} of {$total}",
    ]);
}

// ==========================================
// AJAX HANDLER: Load Hole-by-Hole Scorecard
// ==========================================
add_action('wp_ajax_gh_load_scorecard', 'gh_load_scorecard');
add_action('wp_ajax_nopriv_gh_load_scorecard', 'gh_load_scorecard');
function gh_load_scorecard() {
    check_ajax_referer('gh_ajax_nonce', 'gh_nonce');
    global $wpdb;
    $score_id = (int) $_POST['score_id'];

    $holes = $wpdb->get_results($wpdb->prepare("SELECT * FROM view_golf_hole_by_hole WHERE score_id = %d ORDER BY hole_number ASC", $score_id), ARRAY_A);

    if (!$holes || count($holes) === 0) {
        wp_send_json_error('Hole-by-hole data has not been synced from England Golf for this round yet.');
    }

    $h_data = [];
    $out = ['par'=>0, 'gross'=>0, 'nett'=>0, 'pts'=>0];
    $in  = ['par'=>0, 'gross'=>0, 'nett'=>0, 'pts'=>0];
    $tot = ['par'=>0, 'gross'=>0, 'nett'=>0, 'pts'=>0];

    foreach($holes as $h) {
        $hn = (int)$h['hole_number'];
        $h_data[$hn] = $h;
        if($hn <= 9) {
            $out['par'] += $h['par']; $out['gross'] += $h['gross_score']; $out['nett'] += $h['nett_score']; $out['pts'] += $h['stableford_score'];
        } else {
            $in['par'] += $h['par']; $in['gross'] += $h['gross_score']; $in['nett'] += $h['nett_score']; $in['pts'] += $h['stableford_score'];
        }
        $tot['par'] += $h['par']; $tot['gross'] += $h['gross_score']; $tot['nett'] += $h['nett_score']; $tot['pts'] += $h['stableford_score'];
    }

    $get_circle = function($gross, $par) {
        if (!$gross) return '-';
        $diff = $gross - $par;
        if ($diff <= -2) $class = 'eg-eagle';
        elseif ($diff == -1) $class = 'eg-birdie';
        elseif ($diff == 0)  $class = 'eg-par';
        elseif ($diff == 1)  $class = 'eg-bogey';
        else                 $class = 'eg-double';
        return "<span class='eg-circle {$class}'>{$gross}</span>";
    };

    ob_start();
    ?>
    <div class="eg-scorecard-wrap">
        <table class="eg-scorecard">
            <thead>
                <tr>
                    <th>Hole</th>
                    <?php for($i=1;$i<=9;$i++) echo "<th>$i</th>"; ?>
                    <th class="eg-split">OUT</th>
                    <?php for($i=10;$i<=18;$i++) echo "<th>$i</th>"; ?>
                    <th class="eg-split">IN</th>
                    <th class="eg-tot">TOT</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="eg-label">Par</td>
                    <?php for($i=1;$i<=9;$i++) echo "<td>{$h_data[$i]['par']}</td>"; ?>
                    <td class="eg-split"><?php echo $out['par']; ?></td>
                    <?php for($i=10;$i<=18;$i++) echo "<td>{$h_data[$i]['par']}</td>"; ?>
                    <td class="eg-split"><?php echo $in['par']; ?></td>
                    <td class="eg-tot"><?php echo $tot['par']; ?></td>
                </tr>
                <tr>
                    <td class="eg-label">S.I.</td>
                    <?php for($i=1;$i<=9;$i++) echo "<td>{$h_data[$i]['si']}</td>"; ?>
                    <td class="eg-split">-</td>
                    <?php for($i=10;$i<=18;$i++) echo "<td>{$h_data[$i]['si']}</td>"; ?>
                    <td class="eg-split">-</td>
                    <td class="eg-tot">-</td>
                </tr>
                <tr>
                    <td class="eg-label" style="color:#137a3d;">Shots</td>
                    <?php for($i=1;$i<=9;$i++) echo "<td style='color:#137a3d;'>{$h_data[$i]['shots']}</td>"; ?>
                    <td class="eg-split">-</td>
                    <?php for($i=10;$i<=18;$i++) echo "<td style='color:#137a3d;'>{$h_data[$i]['shots']}</td>"; ?>
                    <td class="eg-split">-</td>
                    <td class="eg-tot">-</td>
                </tr>
                <tr>
                    <td class="eg-label" style="font-weight:bold;">Gross</td>
                    <?php for($i=1;$i<=9;$i++) echo "<td>" . $get_circle($h_data[$i]['gross_score'], $h_data[$i]['par']) . "</td>"; ?>
                    <td class="eg-split" style="font-weight:bold;"><?php echo $out['gross']; ?></td>
                    <?php for($i=10;$i<=18;$i++) echo "<td>" . $get_circle($h_data[$i]['gross_score'], $h_data[$i]['par']) . "</td>"; ?>
                    <td class="eg-split" style="font-weight:bold;"><?php echo $in['gross']; ?></td>
                    <td class="eg-tot" style="font-weight:bold;"><?php echo $tot['gross']; ?></td>
                </tr>
                <tr>
                    <td class="eg-label">Nett</td>
                    <?php for($i=1;$i<=9;$i++) echo "<td>{$h_data[$i]['nett_score']}</td>"; ?>
                    <td class="eg-split"><?php echo $out['nett']; ?></td>
                    <?php for($i=10;$i<=18;$i++) echo "<td>{$h_data[$i]['nett_score']}</td>"; ?>
                    <td class="eg-split"><?php echo $in['nett']; ?></td>
                    <td class="eg-tot"><?php echo $tot['nett']; ?></td>
                </tr>
                <tr>
                    <td class="eg-label">Points</td>
                    <?php for($i=1;$i<=9;$i++) echo "<td>{$h_data[$i]['stableford_score']}</td>"; ?>
                    <td class="eg-split" style="font-weight:bold;"><?php echo $out['pts']; ?></td>
                    <?php for($i=10;$i<=18;$i++) echo "<td>{$h_data[$i]['stableford_score']}</td>"; ?>
                    <td class="eg-split" style="font-weight:bold;"><?php echo $in['pts']; ?></td>
                    <td class="eg-tot" style="font-weight:bold;"><?php echo $tot['pts']; ?></td>
                </tr>
            </tbody>
        </table>
    </div>
    <?php
    wp_send_json_success(ob_get_clean());
}