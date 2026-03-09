<?php
/* ======================================================
   GOLF WHAT IF CALCULATOR
   Shortcode: [golf_what_if]
   Uses ghost score method — inserts a temporary score,
   reads view_handicap_index + view_playing_handicaps,
   then immediately deletes it. Perfectly mirrors live system.
   ====================================================== */

add_shortcode('golf_what_if', function () {
    global $wpdb;

    $players = $wpdb->get_results(
        "SELECT player_id, name FROM {$wpdb->prefix}golf_players ORDER BY name"
    );

    $tees = $wpdb->get_results(
        "SELECT tee_id, tee_colour FROM {$wpdb->prefix}golf_tees
         WHERE course_id = 1 AND tee_colour IN ('White','Yellow','Black')
         ORDER BY slope_rating DESC"
    );

    ob_start();
    ?>
    <div class="golf-whatif-wrap">

        <div class="whatif-form">
            <div class="whatif-row">
                <label>Player</label>
                <select id="wi-player">
                    <option value="">Select player...</option>
                    <?php foreach ($players as $p): ?>
                        <option value="<?php echo esc_attr($p->player_id); ?>">
                            <?php echo esc_html($p->name); ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="whatif-row">
                <label>Tee</label>
                <select id="wi-tee">
                    <?php foreach ($tees as $t): ?>
                        <option value="<?php echo esc_attr($t->tee_id); ?>">
                            <?php echo esc_html($t->tee_colour); ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="whatif-row">
                <label>Gross Score</label>
                <input type="number" id="wi-gross" placeholder="e.g. 88" min="50" max="130">
            </div>
            <button class="golf-btn btn-save" id="wi-calc-btn" type="button" onclick="golfWhatIfCalc()">
                CALCULATE
            </button>
        </div>

        <div id="wi-error" class="wi-error-box" style="display:none;"></div>

        <div id="wi-results" style="display:none;">
            <div class="whatif-result-grid" id="wi-result-inner"></div>
        </div>

    </div>

    <script>
    function golfWhatIfCalc() {
        var player = document.getElementById('wi-player').value;
        var tee    = document.getElementById('wi-tee').value;
        var gross  = document.getElementById('wi-gross').value;

        var errEl = document.getElementById('wi-error');
        var resEl = document.getElementById('wi-results');

        errEl.style.display = 'none';
        resEl.style.display = 'none';

        if (!player || !gross) {
            errEl.textContent = 'Please select a player and enter a gross score.';
            errEl.style.display = 'block';
            return;
        }

        var btn = document.getElementById('wi-calc-btn');
        btn.textContent = 'CALCULATING...';
        btn.disabled = true;

        var params = new URLSearchParams({
            action:    'golf_what_if_calculate',
            nonce:     GolfMasterAjax.nonce,
            player_id: player,
            tee_id:    tee,
            gross:     gross
        });

        fetch(GolfMasterAjax.ajaxUrl, {
            method:  'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body:    params.toString()
        })
        .then(function(r) { return r.json(); })
        .then(function(resp) {
            btn.textContent = 'CALCULATE';
            btn.disabled = false;

            if (!resp.success) {
                errEl.textContent = (resp.data && resp.data.message) ? resp.data.message : 'Calculation error.';
                errEl.style.display = 'block';
                return;
            }

            var d        = resp.data;
            var hiChg    = parseFloat(d.hi_change);
            var hiArrow  = hiChg > 0 ? '&#9650;' : (hiChg < 0 ? '&#9660;' : '&#9679;');
            var hiCls    = hiChg > 0 ? 'wi-up'   : (hiChg < 0 ? 'wi-down' : 'wi-same');
            var hiChgTxt = hiChg > 0 ? '+' + d.hi_change : (hiChg === 0 ? 'No change' : d.hi_change);

            var teeRows = '';
            ['white','yellow','black'].forEach(function(t) {
                var cur    = d.cur_play[t];
                var nw     = d.new_play[t];
                var change = nw - cur;
                var chgTxt = change > 0 ? ('+' + change) : (change < 0 ? '' + change : '&mdash;');
                var chgCls = change > 0 ? 'wi-worse' : (change < 0 ? 'wi-better' : '');
                var label  = t.charAt(0).toUpperCase() + t.slice(1);
                teeRows += '<tr>'
                    + '<td><span class="tee-badge tee-' + t + '">' + label + '</span></td>'
                    + '<td class="tc">' + cur + '</td>'
                    + '<td class="tc"><strong>' + nw + '</strong></td>'
                    + '<td class="tc"><span class="' + chgCls + '">' + chgTxt + '</span></td>'
                    + '</tr>';
            });

            document.getElementById('wi-result-inner').innerHTML =
                '<div class="wi-box wi-diff-box">'
                    + '<div class="wi-label">New Differential</div>'
                    + '<div class="wi-big">' + d.new_diff + '</div>'
                + '</div>'
                + '<div class="wi-box wi-hi-box">'
                    + '<div class="wi-label">Handicap Index</div>'
                    + '<div class="wi-hi-row">'
                        + '<span class="wi-cur">' + d.cur_hi + '</span>'
                        + '<span class="wi-arrow ' + hiCls + '">' + hiArrow + '</span>'
                        + '<span class="wi-new">' + d.new_hi + '</span>'
                    + '</div>'
                    + '<div class="wi-change ' + hiCls + '">' + hiChgTxt + '</div>'
                + '</div>'
                + '<div class="wi-box wi-hcp-box">'
                    + '<div class="wi-label">Playing Handicaps</div>'
                    + '<table class="wi-hcp-table">'
                        + '<thead><tr>'
                            + '<th>Tee</th>'
                            + '<th class="tc">Current</th>'
                            + '<th class="tc">New</th>'
                            + '<th class="tc">Change</th>'
                        + '</tr></thead>'
                        + '<tbody>' + teeRows + '</tbody>'
                    + '</table>'
                + '</div>';

            resEl.style.display = 'block';
        })
        .catch(function() {
            btn.textContent = 'CALCULATE';
            btn.disabled = false;
            errEl.textContent = 'Network error. Please try again.';
            errEl.style.display = 'block';
        });
    }
    </script>
    <?php
    return ob_get_clean();
});


/* ============================
   AJAX: What If Calculate
   Ghost score method — insert, read views, delete.
   ============================ */
add_action('wp_ajax_golf_what_if_calculate',        'golf_what_if_calculate_handler');
add_action('wp_ajax_nopriv_golf_what_if_calculate', 'golf_what_if_calculate_handler');

function golf_what_if_calculate_handler() {
    check_ajax_referer('golf_master_nonce', 'nonce');

    global $wpdb;

    $player_id = isset($_POST['player_id']) ? (int) $_POST['player_id'] : 0;
    $tee_id    = isset($_POST['tee_id'])    ? (int) $_POST['tee_id']    : 0;
    $gross     = isset($_POST['gross'])     ? (int) $_POST['gross']     : 0;

    if (!$player_id || !$tee_id || !$gross) {
        wp_send_json_error(['message' => 'Please fill in all fields.']);
    }

    // Tee data for differential display
    $tee = $wpdb->get_row($wpdb->prepare(
        "SELECT course_rating, slope_rating
         FROM {$wpdb->prefix}golf_tees WHERE tee_id = %d",
        $tee_id
    ));

    if (!$tee) {
        wp_send_json_error(['message' => 'Tee not found.']);
    }

    // New differential for display only
    $new_diff = round(
        ($gross - (float) $tee->course_rating) * (113 / (float) $tee->slope_rating),
        1
    );

    // Snapshot current HI + playing handicaps BEFORE ghost
    $cur_hi_row = $wpdb->get_row($wpdb->prepare(
        "SELECT current_handicap_index FROM view_handicap_index WHERE player_id = %d",
        $player_id
    ));
    $cur_hi = $cur_hi_row ? round((float) $cur_hi_row->current_handicap_index, 1) : 0.0;

    $cur_play_row = $wpdb->get_row($wpdb->prepare(
        "SELECT white_play, yellow_play, black_play
         FROM view_playing_handicaps WHERE player_id = %d",
        $player_id
    ));
    $cur_play = [
        'white'  => $cur_play_row ? (int) $cur_play_row->white_play  : 0,
        'yellow' => $cur_play_row ? (int) $cur_play_row->yellow_play : 0,
        'black'  => $cur_play_row ? (int) $cur_play_row->black_play  : 0,
    ];

    // Insert ghost score — dated today so it sits at the top of the last-20 window
    $inserted = $wpdb->insert(
        $wpdb->prefix . 'golf_scores',
        [
            'player_id'      => $player_id,
            'date_played'    => date('Y-m-d'),
            'tee_id'         => $tee_id,
            'gross_score'    => $gross,
            'pcc_adjustment' => 0,
            'putts'          => 0,
            'gir'            => 0,
            'is_excluded'    => 0,
        ]
    );

    if (!$inserted) {
        wp_send_json_error(['message' => 'Simulation failed — could not write temporary score.']);
    }

    $ghost_id = (int) $wpdb->insert_id;

    // Read new HI + playing handicaps AFTER ghost
    $new_hi_row = $wpdb->get_row($wpdb->prepare(
        "SELECT current_handicap_index FROM view_handicap_index WHERE player_id = %d",
        $player_id
    ));
    $new_hi = $new_hi_row ? round((float) $new_hi_row->current_handicap_index, 1) : $cur_hi;

    $new_play_row = $wpdb->get_row($wpdb->prepare(
        "SELECT white_play, yellow_play, black_play
         FROM view_playing_handicaps WHERE player_id = %d",
        $player_id
    ));
    $new_play = [
        'white'  => $new_play_row ? (int) $new_play_row->white_play  : 0,
        'yellow' => $new_play_row ? (int) $new_play_row->yellow_play : 0,
        'black'  => $new_play_row ? (int) $new_play_row->black_play  : 0,
    ];

    // Always clean up the ghost score
    $wpdb->delete(
        $wpdb->prefix . 'golf_scores',
        ['score_id' => $ghost_id],
        ['%d']
    );

    wp_send_json_success([
        'new_diff'  => $new_diff,
        'cur_hi'    => number_format($cur_hi, 1),
        'new_hi'    => number_format($new_hi, 1),
        'hi_change' => round($new_hi - $cur_hi, 1),
        'cur_play'  => $cur_play,
        'new_play'  => $new_play,
    ]);
}
