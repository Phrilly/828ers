<?php
/* ======================================================
   GOLF MASTER SHORTCODES + AJAX
   Nonce is localised by 828ers.php via wp_localize_script
   as GolfMasterAjax — do NOT redefine it here.
   ====================================================== */

function golf_828ers_can_enter_scores() {
    if (!is_user_logged_in()) return false;
    $user          = wp_get_current_user();
    $allowed_roles = ['administrator', 'editor', 'author', 'golf_member'];
    return (bool) array_intersect($allowed_roles, (array) $user->roles);
}


/* ============================
   1) TOP FORM: 4-Row Entry
   Shortcode: [golf_scorecard_entry]
   ============================ */
add_shortcode('golf_scorecard_entry', function () {
    if (!golf_828ers_can_enter_scores()) {
        return '<p>You do not have permission to enter scores.</p>';
    }

    global $wpdb;

    $players_table = $wpdb->prefix . 'golf_players';
    $tees_table    = $wpdb->prefix . 'golf_tees';

    $players = $wpdb->get_results("SELECT player_id, name FROM {$players_table} ORDER BY name");
    $tees    = $wpdb->get_results("SELECT tee_id, tee_colour FROM {$tees_table} ORDER BY tee_id");

    $default_date = date('Y-m-d');

    ob_start();
    ?>
    <div class="golf-management-root golf-entry-box">

        <div class="golf-grid-header entry-header">
            <div>Player</div>
            <div>Date</div>
            <div>Tee</div>
            <div class="tc">Gross</div>
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

                <div class="field field-gross">
                    <div class="lbl">Gross</div>
                    <input type="number" class="golf-input in-gross tc" placeholder="-">
                </div>

                <input type="hidden" class="golf-input in-pcc" value="0">

                <div class="field field-putts">
                    <div class="lbl">Putts</div>
                    <input type="number" class="golf-input in-putts tc" placeholder="-">
                </div>

                <div class="field field-gir">
                    <div class="lbl">GIR</div>
                    <input type="number" class="golf-input in-gir tc" placeholder="-">
                </div>

                <div class="tc status-cell">-</div>
            </div>
        <?php endfor; ?>

        <div class="entry-footer">
            <button class="golf-btn btn-save" type="button" onclick="golfSaveAll()">SAVE ALL ROUNDS</button>
        </div>
    </div>
    <?php
    return ob_get_clean();
});


/* ============================
   2) BOTTOM GRID: Historic Edit
   Shortcode: [golf_edit_grid]
   ============================ */
add_shortcode('golf_edit_grid', function () {
    if (!golf_828ers_can_enter_scores()) {
        return '<p>You do not have permission to edit scores.</p>';
    }

    global $wpdb;

    $scores_table  = $wpdb->prefix . 'golf_scores';
    $players_table = $wpdb->prefix . 'golf_players';
    $tees_table    = $wpdb->prefix . 'golf_tees';
    $history_view  = 'view_golf_dashboard_history';

    $rounds = $wpdb->get_results("
        SELECT
            s.score_id,
            s.player_id,
            p.name        AS player_name,
            s.date_played,
            s.tee_id,
            t.tee_colour,
            s.gross_score,
            s.pcc_adjustment,
            s.putts,
            s.gir,
            s.is_excluded,
            COALESCE(v.net_score, 0)    AS net_score,
            COALESCE(v.differential, 0) AS differential,
            COALESCE(v.is_counting, 0)  AS is_counting
        FROM      {$scores_table}  s
        JOIN      {$players_table} p ON p.player_id = s.player_id
        JOIN      {$tees_table}    t ON t.tee_id    = s.tee_id
        LEFT JOIN {$history_view}  v ON v.score_id  = s.score_id
        ORDER BY  s.date_played DESC, s.score_id DESC
        LIMIT 30
    ");

    $tees = $wpdb->get_results("SELECT tee_id, tee_colour FROM {$tees_table} ORDER BY tee_id");

    ob_start();
    ?>
    <div class="golf-management-root golf-edit-box">
        <div class="edit-grid-notice" style="padding:10px; margin:0 10px 12px; background:#d1ecf1; border:1px solid #bee5eb; border-radius:4px; font-size:13px; color:#0c5460;">
            💡 <strong>Edit Grid:</strong> Update PCC here the next day (typically -1, 0, +1, +2, or +3).
            <strong>Excl</strong> = round played but not submitted to England Golf — saves for records but excluded from handicap calculation.
            Note: after saving, refresh the page to see updated "counting" dots across all rounds.
        </div>

        <div class="golf-grid-header edit-header">
            <div>Player</div>
            <div>Date</div>
            <div>Tee</div>
            <div class="tc">Gross</div>
            <div class="tc">PCC</div>
            <div class="tc">Putts</div>
            <div class="tc">GIR</div>
            <div class="tc">Excl</div>
            <div class="tc">Nett</div>
            <div class="tc">Action</div>
        </div>

        <?php foreach ($rounds as $r): ?>
            <?php $is_excl = !empty($r->is_excluded) ? 1 : 0; ?>
            <div class="golf-grid-row edit-row <?php echo $is_excl ? 'row-excluded' : ''; ?>"
                 id="row-<?php echo esc_attr($r->score_id); ?>">

                <div><strong><?php echo esc_html($r->player_name); ?></strong></div>

                <input type="date" class="golf-input ed-date"
                       value="<?php echo esc_attr($r->date_played); ?>">

                <select class="golf-input ed-tee">
                    <?php foreach ($tees as $t): ?>
                        <?php $selected = ((int) $r->tee_id === (int) $t->tee_id) ? 'selected' : ''; ?>
                        <option value="<?php echo esc_attr($t->tee_id); ?>" <?php echo $selected; ?>>
                            <?php echo esc_html($t->tee_colour); ?>
                        </option>
                    <?php endforeach; ?>
                </select>

                <input type="number" class="golf-input ed-gross tc"
                       value="<?php echo esc_attr($r->gross_score); ?>">

                <select class="golf-input ed-pcc tc">
                    <?php
                    $pcc_current = (int) $r->pcc_adjustment;
                    foreach ([-1, 0, 1, 2, 3] as $val) {
                        $sel     = ($pcc_current === $val) ? 'selected' : '';
                        $display = ($val > 0) ? "+{$val}" : $val;
                        echo "<option value='{$val}' {$sel}>{$display}</option>";
                    }
                    ?>
                </select>

                <input type="number" class="golf-input ed-putts tc"
                       value="<?php echo esc_attr($r->putts); ?>">
                <input type="number" class="golf-input ed-gir tc"
                       value="<?php echo esc_attr($r->gir); ?>">

                <div class="tc">
                    <input type="checkbox" class="golf-input ed-excl" value="1"
                           <?php checked($is_excl, 1); ?> title="Exclude from handicap">
                </div>

                <div class="computed tc ed-net">
                    <span class="net-val <?php echo ((int) $r->is_counting === 1) ? 'count-circle' : ''; ?>">
                        <?php echo esc_html($r->net_score); ?>
                    </span>
                </div>

                <div class="tc action-btns">
                    <button class="golf-btn btn-save" type="button"
                            onclick="ajaxUpdate(<?php echo (int) $r->score_id; ?>)">SAVE</button>
                    <button class="golf-btn btn-del" type="button"
                            onclick="ajaxDelete(<?php echo (int) $r->score_id; ?>)">DEL</button>
                </div>
            </div>
        <?php endforeach; ?>
    </div>
    <?php
    return ob_get_clean();
});


/* ============================
   3) AJAX: Bulk Save
   ============================ */
add_action('wp_ajax_golf_final_action_bulk_save', function () {
    check_ajax_referer('golf_master_nonce', 'nonce');

    if (!golf_828ers_can_enter_scores()) {
        wp_send_json_error(['message' => 'Unauthorized.']);
    }

    global $wpdb;

    $scores_table  = $wpdb->prefix . 'golf_scores';
    $players_table = $wpdb->prefix . 'golf_players';
    $tees_table    = $wpdb->prefix . 'golf_tees';
    $history_view  = $wpdb->prefix . 'golf_dashboard_history';

    $rounds       = (isset($_POST['rounds']) && is_array($_POST['rounds'])) ? $_POST['rounds'] : [];
    $inserted_ids = [];

    foreach ($rounds as $r) {
        $player = isset($r['player_id']) ? (int) $r['player_id'] : 0;
        $tee    = isset($r['tee'])       ? (int) $r['tee']       : 0;
        $gross  = isset($r['gross'])     ? (int) $r['gross']      : 0;
        $date   = isset($r['date'])      ? sanitize_text_field($r['date']) : '';

        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) continue;
        if (!$player || !$tee || !$gross) continue;

        $ok = $wpdb->insert($scores_table, [
            'player_id'      => $player,
            'date_played'    => $date,
            'tee_id'         => $tee,
            'gross_score'    => $gross,
            'pcc_adjustment' => 0,
            'putts'          => isset($r['putts']) ? (int) $r['putts'] : 0,
            'gir'            => isset($r['gir'])   ? (int) $r['gir']   : 0,
            'is_excluded'    => 0,
        ]);

        if ($ok) {
            $inserted_ids[] = (int) $wpdb->insert_id;
        }
    }

    if (!$inserted_ids) {
        wp_send_json_error(['message' => 'No valid rounds to save.']);
    }

    $placeholders = implode(',', array_fill(0, count($inserted_ids), '%d'));
    $rows = $wpdb->get_results(
        $wpdb->prepare(
            "SELECT s.score_id, p.name AS player_name, s.date_played,
                    t.tee_colour, s.tee_id, s.gross_score, s.pcc_adjustment,
                    s.putts, s.gir, s.is_excluded,
                    COALESCE(h.net_score, 0)    AS net_score,
                    COALESCE(h.differential, 0) AS differential,
                    COALESCE(h.is_counting, 0)  AS is_counting
             FROM      {$scores_table}  s
             JOIN      {$players_table} p ON p.player_id = s.player_id
             JOIN      {$tees_table}    t ON t.tee_id    = s.tee_id
             LEFT JOIN {$history_view}  h ON h.score_id  = s.score_id
             WHERE s.score_id IN ({$placeholders})
             ORDER BY s.date_played DESC, s.score_id DESC",
            ...$inserted_ids
        )
    );

    wp_send_json_success(['inserted_ids' => $inserted_ids, 'rows' => $rows]);
});


/* ============================
   4) AJAX: Delete
   ============================ */
add_action('wp_ajax_golf_final_action_delete', function () {
    check_ajax_referer('golf_master_nonce', 'nonce');

    if (!golf_828ers_can_enter_scores()) {
        wp_send_json_error(['message' => 'Unauthorized.']);
    }

    global $wpdb;

    $score_id = isset($_POST['score_id']) ? (int) $_POST['score_id'] : 0;
    if (!$score_id) {
        wp_send_json_error(['message' => 'Invalid score_id']);
    }

    $deleted = $wpdb->delete(
        $wpdb->prefix . 'golf_scores',
        ['score_id' => $score_id],
        ['%d']
    );

    if ($deleted === false) {
        wp_send_json_error(['message' => 'Database delete failed', 'db_error' => $wpdb->last_error]);
    }
    if ($deleted === 0) {
        wp_send_json_error(['message' => 'No rows deleted', 'score_id' => $score_id]);
    }

    wp_send_json_success(['deleted' => (int) $deleted, 'score_id' => $score_id]);
});


/* ============================
   5) AJAX: Update
   ============================ */
add_action('wp_ajax_golf_final_action_update', function () {
    check_ajax_referer('golf_master_nonce', 'nonce');

    if (!golf_828ers_can_enter_scores()) {
        wp_send_json_error(['message' => 'Unauthorized.']);
    }

    global $wpdb;

    $scores_table = $wpdb->prefix . 'golf_scores';
    $history_view = $wpdb->prefix . 'golf_dashboard_history';

    $score_id = isset($_POST['score_id']) ? (int) $_POST['score_id'] : 0;
    if (!$score_id) {
        wp_send_json_error(['message' => 'Invalid score_id']);
    }

    $new_date = isset($_POST['date']) ? sanitize_text_field($_POST['date']) : '';
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $new_date)) {
        $new_date = current_time('Y-m-d');
    }

    $is_excluded = isset($_POST['excluded']) ? (int) (bool) $_POST['excluded'] : 0;

    $updated = $wpdb->update(
        $scores_table,
        [
            'date_played'    => $new_date,
            'tee_id'         => isset($_POST['tee'])   ? (int) $_POST['tee']   : 0,
            'gross_score'    => isset($_POST['gross'])  ? (int) $_POST['gross']  : 0,
            'pcc_adjustment' => isset($_POST['pcc'])    ? (int) $_POST['pcc']    : 0,
            'putts'          => isset($_POST['putts'])  ? (int) $_POST['putts']  : 0,
            'gir'            => isset($_POST['gir'])    ? (int) $_POST['gir']    : 0,
            'is_excluded'    => $is_excluded,
        ],
        ['score_id' => $score_id],
        null,
        ['%d']
    );

    if ($updated === false) {
        wp_send_json_error(['message' => 'Database update failed', 'db_error' => $wpdb->last_error]);
    }

    $row = $wpdb->get_row(
        $wpdb->prepare(
            "SELECT score_id, net_score, differential, is_counting
             FROM {$history_view} WHERE score_id = %d",
            $score_id
        )
    );

    // FIXED: properly distinguish excluded rounds from genuinely missing rows
    if (!$row) {
        if ($is_excluded) {
            // Correctly excluded — not in WHS view by design
            wp_send_json_success([
                'score_id'     => $score_id,
                'net_score'    => '-',
                'differential' => '-',
                'is_counting'  => 0,
                'is_excluded'  => 1,
            ]);
        } else {
            // Row missing for unknown reason — surface it for debugging
            wp_send_json_error(['message' => 'Updated but WHS view row not found. Try refreshing.']);
        }
    }

    wp_send_json_success([
        'score_id'     => (int) $row->score_id,
        'net_score'    => $row->net_score,
        'differential' => $row->differential,
        'is_counting'  => (int) $row->is_counting,
        'is_excluded'  => $is_excluded,
    ]);
});