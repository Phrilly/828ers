<?php
/**
 * Golf Rounds Pivot
 * Shortcode: [golf_rounds_pivot]
 * AJAX endpoint: grp5_load (admin-ajax.php)
 *
 * Assumes a DB view named: view_golf_rounds_pivot
 */

add_shortcode('golf_rounds_pivot', function () {
    $nonce = wp_create_nonce('grp5_nonce');

    ob_start();
    ?>
    <div id="grp5-app" class="grp5">
        <div class="grp5-range" id="grp5-range"></div>
        <div class="grp5-tablewrap" id="grp5-tablewrap">
            <div class="grp5-loading">Loading…</div>
        </div>
        <div class="grp5-pager" id="grp5-pager"></div>
    </div>

    <script>
    (function () {
        const app   = document.getElementById('grp5-app');
        const wrap  = document.getElementById('grp5-tablewrap');
        const pager = document.getElementById('grp5-pager');
        const range = document.getElementById('grp5-range');

        function loadPage(page) {
            wrap.classList.add('is-loading');

            fetch('<?php echo esc_url(admin_url('admin-ajax.php')); ?>', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
                body: new URLSearchParams({
                    action: 'grp5_load',
                    page: page,
                    nonce: '<?php echo esc_js($nonce); ?>'
                })
            })
            .then(r => r.json())
            .then(d => {
                if (!d || !d.success) {
                    wrap.innerHTML = '<div class="grp5-error">Error loading rounds.</div>';
                    wrap.classList.remove('is-loading');
                    return;
                }
                wrap.innerHTML = d.data.table;
                pager.innerHTML = d.data.pagination;
                range.textContent = d.data.range;
                wrap.classList.remove('is-loading');
            })
            .catch(() => {
                wrap.innerHTML = '<div class="grp5-error">Error loading rounds.</div>';
                wrap.classList.remove('is-loading');
            });
        }

        pager.addEventListener('click', (e) => {
            const el = e.target.closest('[data-page]');
            if (!el) return;

            const p = parseInt(el.dataset.page, 10);
            if (!p) return;

            if (el.classList.contains('disabled') || el.getAttribute('aria-disabled') === 'true') return;
            if (el.classList.contains('current')) return;

            e.preventDefault();
            loadPage(p);
            app.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });

        loadPage(1);
    })();
    </script>
    <?php

    return ob_get_clean();
});

add_action('wp_ajax_grp5_load', 'grp5_load');
add_action('wp_ajax_nopriv_grp5_load', 'grp5_load');

function grp5_load() {
    check_ajax_referer('grp5_nonce', 'nonce');
    global $wpdb;

    $view   = 'view_golf_rounds_pivot';
    $limit  = 50;
    $page   = max(1, (int) ($_POST['page'] ?? 1));
    $offset = ($page - 1) * $limit;

    // Fetch player IDs dynamically — never hardcode [1, 2, 3, 4]
    $players_table = $wpdb->prefix . 'golf_players';
    $playerRows    = $wpdb->get_results(
        "SELECT player_id, name FROM {$players_table} ORDER BY player_id ASC",
        OBJECT_K
    );
    $playerIds = array_keys($playerRows);

    // Total rows for paging
    $total      = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$view}");
    $totalPages = max(1, (int) ceil($total / $limit));

    $page   = min($page, $totalPages);
    $offset = ($page - 1) * $limit;

    $startRow = $total ? ($offset + 1) : 0;
    $endRow   = min($offset + $limit, $total);

    // Fetch page rows
    $rows = $wpdb->get_results($wpdb->prepare("
        SELECT *
        FROM {$view}
        ORDER BY date_played DESC, tee_colour ASC
        LIMIT %d OFFSET %d
    ", $limit, $offset), ARRAY_A);

    // Build labels map from the dynamic query results
    $labels = [];
    foreach ($playerIds as $pid) {
        $labels[$pid] = $playerRows[$pid]->name ?? ('P' . $pid);
    }

    // Render table
    ob_start();
    ?>
    <div class="grp5-tablewrap-inner">
        <table class="grp5-table">
            <thead>
                <tr>
                    <th rowspan="2" class="sticky col-date">Date</th>
                    <th rowspan="2" class="sticky col-tee">Tee</th>
                    <?php foreach ($playerIds as $pid): ?>
                        <th colspan="3" class="sticky grp5-ph"><?php echo esc_html($labels[$pid] ?? ('P' . $pid)); ?></th>
                    <?php endforeach; ?>
                    <th rowspan="2" class="sticky col-winner">Winner</th>
                </tr>
                <tr>
                    <?php foreach ($playerIds as $pid): ?>
                        <th class="sticky tc sub">Gross</th>
                        <th class="sticky tc sub">Hcp</th>
                        <th class="sticky tc sub">Nett</th>
                    <?php endforeach; ?>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($rows)): ?>
                    <tr><td colspan="<?php echo esc_attr(3 + (count($playerIds) * 3)); ?>">No rounds found.</td></tr>
                <?php else: ?>
                    <?php foreach ($rows as $r): ?>
                        <?php
                        $winner = (string) ($r['winner'] ?? '');
                        $wcol   = (string) ($r['winner_colour'] ?? '');

                        $winnerClasses = ['col-winner'];
                        $winnerAttrs   = '';

                        if ($winner === 'TIE') {
                            $winnerClasses[] = 'is-tie';
                            $winnerAttrs    .= ' data-winner="TIE"';
                        } elseif ($wcol !== '') {
                            $winnerClasses[] = 'is-' . sanitize_html_class($wcol);
                            $winnerAttrs    .= ' data-winner-colour="' . esc_attr($wcol) . '"';
                        }
                        ?>
                        <tr>
                            <td class="col-date"><?php echo esc_html(date('j M Y', strtotime($r['date_played']))); ?></td>
                            <td class="col-tee"><?php echo esc_html($r['tee_colour'] ?? ''); ?></td>

                            <?php foreach ($playerIds as $pid): ?>
                                <td class="tc"><?php echo esc_html($r['p' . $pid . '_gross'] ?? ''); ?></td>
                                <td class="tc"><?php echo esc_html($r['p' . $pid . '_hcp'] ?? ''); ?></td>
                                <td class="tc"><?php echo esc_html($r['p' . $pid . '_net'] ?? ''); ?></td>
                            <?php endforeach; ?>

                            <td class="<?php echo esc_attr(implode(' ', $winnerClasses)); ?>"<?php echo $winnerAttrs; ?>>
                                <?php echo esc_html($winner); ?>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
    <?php
    $tableHtml = ob_get_clean();

    // Render pagination
    ob_start();
    if ($totalPages > 1) {
        $prevPage = max(1, $page - 1);
        $nextPage = min($totalPages, $page + 1);

        if ($page > 1) {
            echo '<a class="grp5-page prev" href="#" data-page="' . esc_attr($prevPage) . '">Prev</a>';
        } else {
            echo '<span class="grp5-page prev disabled" aria-disabled="true">Prev</span>';
        }

        echo '<span class="grp5-page current" aria-current="page">' . esc_html($page) . '</span>';
        echo '<span class="grp5-page of">of</span>';
        echo '<span class="grp5-page total">' . esc_html($totalPages) . '</span>';

        if ($page < $totalPages) {
            echo '<a class="grp5-page next" href="#" data-page="' . esc_attr($nextPage) . '">Next</a>';
        } else {
            echo '<span class="grp5-page next disabled" aria-disabled="true">Next</span>';
        }
    }
    $paginationHtml = ob_get_clean();

    wp_send_json_success([
        'table'      => $tableHtml,
        'pagination' => $paginationHtml,
        'range'      => "Showing {$startRow}–{$endRow} of {$total}",
    ]);
}
