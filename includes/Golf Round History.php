<?php
/**
 * Golf Round History
 * Shortcode: [golf_round_history]
 * AJAX action: gh_load_history
 */


add_shortcode('golf_round_history', function () {
    global $wpdb;


    $players_table = $wpdb->prefix . 'golf_players';


    // Fetch players for the dropdown
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


    $where_sql = '';
    $where_args = [];
    if ($player) {
        $where_sql = 'WHERE player_id = %d';
        $where_args[] = $player;
    }


    // Total rows
    if ($where_sql) {
        $total = (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$history_view} {$where_sql}", ...$where_args));
    } else {
        $total = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$history_view}");
    }


    // Rows
    if ($where_sql) {
        $sql = $wpdb->prepare(
            "SELECT * FROM {$history_view} {$where_sql} ORDER BY date_played DESC LIMIT %d OFFSET %d",
            ...array_merge($where_args, [$limit, $offset])
        );
    } else {
        $sql = $wpdb->prepare(
            "SELECT * FROM {$history_view} ORDER BY date_played DESC LIMIT %d OFFSET %d",
            $limit,
            $offset
        );
    }


    $rows = $wpdb->get_results($sql, ARRAY_A);


    $total_pages = max(1, (int) ceil($total / $limit));
    $start_row   = $total ? ($offset + 1) : 0;
    $end_row     = min($offset + $limit, $total);


    // Table HTML
    ob_start();
    ?>
    <table class="history-table">
        <thead>
            <tr>
                <th>Date</th><th>Player</th><th>Tee</th>
                <th class="tc">HI</th>
                <th class="tc">Gross</th><th class="tc">Nett</th>
                <th class="tc">Diff</th><th class="tc">Putts</th>
                <th class="tc">GIR</th><th class="tc">Adj</th>
                <th class="tc">Excl</th><th class="tc">Count</th>
            </tr>
        </thead>
        <tbody>
        <?php if ($rows): ?>
            <?php foreach ($rows as $r): ?>
                <?php
                $cap = !empty($r['cap_applied']);
                $esr = !empty($r['esr_applied']);

                $row_class = '';
                if ($cap) $row_class .= ' is-cap';
                if ($esr) $row_class .= ' is-esr';
                if (!empty($r['is_excluded'])) $row_class .= ' is-excluded';

                $adj = '';
                if ($esr) $adj .= 'E';
                if ($cap) $adj .= 'C';

                $hi = isset($r['starting_index']) ? number_format((float)$r['starting_index'], 1) : '-';
                ?>
                <tr class="<?php echo esc_attr(trim($row_class)); ?>">
                    <td><?php echo esc_html(date('j M Y', strtotime($r['date_played']))); ?></td>
                    <td><strong><?php echo esc_html($r['player_name']); ?></strong></td>
                    <td>
                        <span class="tee-badge tee-<?php echo esc_attr(strtolower($r['tee_colour'] ?? '')); ?>">
                            <?php echo esc_html($r['tee_colour'] ?? ''); ?>
                        </span>
                    </td>

                    <td class="tc"><?php echo esc_html($hi); ?></td>
                    <td class="tc"><?php echo (int) ($r['gross_score'] ?? 0); ?></td>
                    <td class="tc"><?php echo (int) ($r['net_score'] ?? 0); ?></td>
                    <td class="tc"><?php echo esc_html(number_format((float) ($r['differential'] ?? 0), 1)); ?></td>
                    <td class="tc"><?php echo (int) ($r['putts'] ?? 0); ?></td>
                    <td class="tc"><?php echo (int) ($r['gir'] ?? 0); ?></td>

                    <td class="tc">
                        <?php if ($adj !== ''): ?>
                            <span class="adj-badge"><?php echo esc_html($adj); ?></span>
                        <?php endif; ?>
                    </td>

                    <td class="tc">
                        <?php if (!empty($r['is_excluded'])): ?>
                            <span class="excl-badge" title="Excluded from handicap">X</span>
                        <?php endif; ?>
                    </td>

                    <td class="tc"><?php echo !empty($r['is_counting']) ? '<span class="counting-dot"></span>' : ''; ?></td>
                </tr>
            <?php endforeach; ?>
        <?php else: ?>
            <tr><td colspan="12">No rounds found.</td></tr>
        <?php endif; ?>
        </tbody>
    </table>
    <?php
    $table_html = ob_get_clean();


    // Pagination HTML
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
