
/* ======================================================
   GOLF MASTER SHORTCODES + AJAX
   (Entry form + Edit grid + Save/Update/Delete)
   ====================================================== */

/* ============================
   1) TOP FORM: 4-Row Entry
   Shortcode: [golf_scorecard_entry]
   ============================ */
add_shortcode('golf_scorecard_entry', function() {
    global $wpdb;

    $players_table = $wpdb->prefix . 'golf_players';
    $tees_table    = $wpdb->prefix . 'golf_tees';

    $players = $wpdb->get_results("SELECT player_id, name FROM {$players_table} ORDER BY name");
    $tees    = $wpdb->get_results("SELECT tee_id, tee_colour FROM {$tees_table} ORDER BY tee_id");

    $default_date = date('Y-m-d');

    ob_start(); ?>
    <div class="golf-management-root golf-entry-box">
        <div class="golf-grid-header entry-header">
            <div>Player</div>
            <div>Date</div>
            <div>Tee</div>
            <div class="tc">Gross</div>
            <div class="tc">PCC</div>
            <div class="tc">Putts</div>
            <div class="tc">GIR</div>
            <div class="tc">Status</div>
        </div>

        <?php for ($i = 0; $i < 4; $i++): ?>
        <div class="golf-grid-row entry-row">
            <select class="golf-input in-player">
                <option value="">Player...</option>
                <?php foreach ($players as $p): ?>
                    <option value="<?php echo esc_attr($p->player_id); ?>">
                        <?php echo esc_html($p->name); ?>
                    </option>
                <?php endforeach; ?>
            </select>

            <input type="date" class="golf-input in-date" value="<?php echo esc_attr($default_date); ?>">

            <!-- Tee (wrapped for mobile label) -->
            <div class="field field-tee">
                <div class="lbl">Tee</div>
                <select class="golf-input in-tee">
                    <?php foreach ($tees as $t): ?>
                        <option value="<?php echo esc_attr($t->tee_id); ?>">
                            <?php echo esc_html($t->tee_colour); ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>

            <!-- Gross (wrapped for mobile label) -->
            <div class="field field-gross">
                <div class="lbl">Gross</div>
                <input type="number" class="golf-input in-gross tc" placeholder="-">
            </div>

            <input type="number" class="golf-input in-pcc tc" value="0">

            <!-- Putts (wrapped for mobile label) -->
            <div class="field field-putts">
                <div class="lbl">Putts</div>
                <input type="number" class="golf-input in-putts tc" placeholder="-">
            </div>

            <!-- GIR (wrapped for mobile label) -->
            <div class="field field-gir">
                <div class="lbl">GIR</div>
                <input type="number" class="golf-input in-gir tc" placeholder="-">
            </div>

            <div class="tc status-cell">-</div>
        </div>
        <?php endfor; ?>

        <div class="entry-footer">
            <button class="golf-btn btn-save" onclick="golfSaveAll()">SAVE ALL ROUNDS</button>
        </div>
    </div>
    <?php return ob_get_clean();
});


/* ============================
   2) BOTTOM GRID: Historic Edit
   Shortcode: [golf_edit_grid]
   ============================ */
add_shortcode('golf_edit_grid', function() {
    global $wpdb;

    $history_view = $wpdb->prefix . 'golf_dashboard_history';
    $tees_table   = $wpdb->prefix . 'golf_tees';

    $rounds = $wpdb->get_results("SELECT * FROM {$history_view} ORDER BY date_played DESC, score_id DESC LIMIT 30");
    $tees   = $wpdb->get_results("SELECT tee_id, tee_colour FROM {$tees_table} ORDER BY tee_id");

    ob_start(); ?>
    <div class="golf-management-root golf-edit-box">
        <div class="golf-grid-header edit-header">
            <div>Player</div>
            <div>Date</div>
            <div>Tee</div>
            <div class="tc">Gross</div>
            <div class="tc">PCC</div>
            <div class="tc">Putts</div>
            <div class="tc">GIR</div>
            <div class="tc">Nett</div>
            <div class="tc">Diff</div>
            <div class="tc">Count</div>
            <div class="tc">Action</div>
        </div>

        <?php foreach ($rounds as $r): ?>
        <div class="golf-grid-row edit-row" id="row-<?php echo esc_attr($r->score_id); ?>">
            <div><strong><?php echo esc_html($r->player_name); ?></strong></div>

            <input type="date" class="golf-input ed-date" value="<?php echo esc_attr($r->date_played); ?>">

            <select class="golf-input ed-tee">
                <?php foreach ($tees as $t): ?>
                    <?php $selected = ((int)$r->tee_id === (int)$t->tee_id) ? 'selected' : ''; ?>
                    <option value="<?php echo esc_attr($t->tee_id); ?>" <?php echo $selected; ?>>
                        <?php echo esc_html($t->tee_colour); ?>
                    </option>
                <?php endforeach; ?>
            </select>

            <input type="number" class="golf-input ed-gross tc" value="<?php echo esc_attr($r->gross_score); ?>">
            <input type="number" class="golf-input ed-pcc tc"   value="<?php echo esc_attr($r->pcc_adjustment); ?>">
            <input type="number" class="golf-input ed-putts tc" value="<?php echo esc_attr($r->putts); ?>">
            <input type="number" class="golf-input ed-gir tc"   value="<?php echo esc_attr($r->gir); ?>">

            <div class="computed tc ed-net"><?php echo esc_html($r->net_score); ?></div>
            <div class="computed tc ed-diff"><?php echo esc_html($r->differential); ?></div>

            <div class="tc ed-count">
                <?php if ((int)$r->is_counting === 1): ?>
                    <span class="count-dot" aria-label="Counting round"></span>
                <?php endif; ?>
            </div>

            <div class="tc action-btns">
                <button class="golf-btn btn-save" onclick="ajaxUpdate(<?php echo (int)$r->score_id; ?>)">SAVE</button>
                <button class="golf-btn btn-del"  onclick="ajaxDelete(<?php echo (int)$r->score_id; ?>)">DEL</button>
            </div>
        </div>
        <?php endforeach; ?>
    </div>
    <?php return ob_get_clean();
});


/* ============================
   3) AJAX Receivers
   ============================ */
add_action('wp_ajax_golf_final_action_bulk_save', function() {
    global $wpdb;

    $scores_table = $wpdb->prefix . 'golf_scores';
    $history_view = $wpdb->prefix . 'golf_dashboard_history';

    $rounds = isset($_POST['rounds']) && is_array($_POST['rounds']) ? $_POST['rounds'] : [];
    $inserted_ids = [];

    foreach ($rounds as $r) {
        $player = isset($r['player_id']) ? (int)$r['player_id'] : 0;
        $date   = isset($r['date']) ? sanitize_text_field($r['date']) : '';
        $tee    = isset($r['tee']) ? (int)$r['tee'] : 0;
        $gross  = isset($r['gross']) ? (int)$r['gross'] : 0;

        if (!$player || !$date || !$tee || !$gross) continue;

        $ok = $wpdb->insert($scores_table, [
            'player_id'      => $player,
            'date_played'    => $date,
            'tee_id'         => $tee,
            'gross_score'    => $gross,
            'pcc_adjustment' => isset($r['pcc']) ? (int)$r['pcc'] : 0,
            'putts'          => isset($r['putts']) ? (int)$r['putts'] : 0,
            'gir'            => isset($r['gir']) ? (int)$r['gir'] : 0,
        ]);

        if ($ok) $inserted_ids[] = (int)$wpdb->insert_id;
    }

    if (!$inserted_ids) {
        wp_send_json_error(['message' => 'No valid rounds to save.']);
    }

    $placeholders = implode(',', array_fill(0, count($inserted_ids), '%d'));
    $query = $wpdb->prepare(
        "SELECT * FROM {$history_view} WHERE score_id IN ($placeholders) ORDER BY date_played DESC, score_id DESC",
        ...$inserted_ids
    );
    $rows = $wpdb->get_results($query);

    wp_send_json_success(['inserted_ids' => $inserted_ids, 'rows' => $rows]);
});

add_action('wp_ajax_golf_final_action_delete', function() {
    global $wpdb;

    $scores_table = $wpdb->prefix . 'golf_scores';
    $score_id = isset($_POST['score_id']) ? (int)$_POST['score_id'] : 0;

    if (!$score_id) wp_send_json_error(['message' => 'Invalid score_id']);

    $deleted = $wpdb->delete($scores_table, ['score_id' => $score_id], ['%d']);

    if ($deleted === false) wp_send_json_error(['message' => 'Database delete failed', 'dberror' => $wpdb->last_error]);
    if ($deleted === 0)     wp_send_json_error(['message' => 'No rows deleted (not found)', 'score_id' => $score_id]);

    wp_send_json_success(['deleted' => (int)$deleted, 'score_id' => $score_id]);
});

add_action('wp_ajax_golf_final_action_update', function() {
    global $wpdb;

    $scores_table = $wpdb->prefix . 'golf_scores';
    $history_view = $wpdb->prefix . 'golf_dashboard_history';

    $score_id = isset($_POST['score_id']) ? (int)$_POST['score_id'] : 0;
    if (!$score_id) wp_send_json_error(['message' => 'Invalid score_id']);

    $wpdb->update($scores_table, [
        'date_played'    => isset($_POST['date']) ? sanitize_text_field($_POST['date']) : '',
        'tee_id'         => isset($_POST['tee']) ? (int)$_POST['tee'] : 0,
        'gross_score'    => isset($_POST['gross']) ? (int)$_POST['gross'] : 0,
        'pcc_adjustment' => isset($_POST['pcc']) ? (int)$_POST['pcc'] : 0,
        'putts'          => isset($_POST['putts']) ? (int)$_POST['putts'] : 0,
        'gir'            => isset($_POST['gir']) ? (int)$_POST['gir'] : 0,
    ], ['score_id' => $score_id], null, ['%d']);

    $row = $wpdb->get_row($wpdb->prepare("SELECT score_id, net_score, differential, is_counting FROM {$history_view} WHERE score_id = %d", $score_id));
    if (!$row) wp_send_json_error(['message' => 'Updated but view row not found']);

    wp_send_json_success([
        'score_id'      => (int)$row->score_id,
        'net_score'     => $row->net_score,
        'differential'  => $row->differential,
        'is_counting'   => (int)$row->is_counting,
    ]);
});
