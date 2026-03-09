<?php
/* ======================================================
   GOLF WHAT IF CALCULATOR
   Shortcode: [golf_what_if]
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
            <div class="whatif-row">
                <label>PCC</label>
                <select id="wi-pcc">
                    <option value="-2">-2</option>
                    <option value="-1">-1</option>
                    <option value="0" selected>0</option>
                    <option value="1">+1</option>
                    <option value="2">+2</option>
                    <option value="3">+3</option>
                </select>
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
        var pcc    = document.getElementById('wi-pcc').value;

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
            gross:     gross,
            pcc:       pcc
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

            var d       = resp.data;
            var hiChg   = parseFloat(d.hi_change);
            var hiArrow = hiChg > 0 ? '&#9650;' : (hiChg < 0 ? '&#9660;' : '&#9679;');
            var hiCls   = hiChg > 0 ? 'wi-up'   : (hiChg < 0 ? 'wi-down' : 'wi-same');
            var hiChgTxt = hiChg > 0 ? '+' + d.hi_change : d.hi_change;

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
   ============================ */
add_action('wp_ajax_golf_what_if_calculate',        'golf_what_if_calculate_handler');
add_action('wp_ajax_nopriv_golf_what_if_calculate', 'golf_what_if_calculate_handler');

function golf_what_if_calculate_handler() {
    check_ajax_referer('golf_master_nonce', 'nonce');

    global $wpdb;

    $player_id = isset($_POST['player_id']) ? (int) $_POST['player_id'] : 0;
    $tee_id    = isset($_POST['tee_id'])    ? (int) $_POST['tee_id']    : 0;
    $gross     = isset($_POST['gross'])     ? (int) $_POST['gross']     : 0;
    $pcc       = isset($_POST['pcc'])       ? (int) $_POST['pcc']       : 0;

    if (!$player_id || !$tee_id || !$gross) {
        wp_send_json_error(['message' => 'Please fill in all fields.']);
    }

    // Tee used for this round
    $tee = $wpdb->get_row($wpdb->prepare(
        "SELECT tee_colour, course_rating, slope_rating, par
         FROM {$wpdb->prefix}golf_tees WHERE tee_id = %d",
        $tee_id
    ));

    if (!$tee) {
        wp_send_json_error(['message' => 'Tee not found.']);
    }

    // All three Ramsey tees for playing handicap output
    $all_tees = $wpdb->get_results(
        "SELECT tee_colour, course_rating, slope_rating, par
         FROM {$wpdb->prefix}golf_tees
         WHERE course_id = 1 AND tee_colour IN ('White','Yellow','Black')"
    );
    $tees_by_colour = [];
    foreach ($all_tees as $t) {
        $tees_by_colour[$t->tee_colour] = $t;
    }

    // Current HI
    $cur_hi_row = $wpdb->get_row($wpdb->prepare(
        "SELECT current_handicap_index FROM view_handicap_index WHERE player_id = %d",
        $player_id
    ));
    $cur_hi = $cur_hi_row ? (float) $cur_hi_row->current_handicap_index : 0.0;

    // Last 20 non-excluded differentials
    $diffs = $wpdb->get_col($wpdb->prepare(
        "SELECT h.differential
         FROM {$wpdb->prefix}golf_dashboard_history h
         JOIN {$wpdb->prefix}golf_scores s ON s.score_id = h.score_id
         WHERE s.player_id = %d AND s.is_excluded = 0
         ORDER BY s.date_played DESC, s.score_id DESC
         LIMIT 20",
        $player_id
    ));
    $diffs = array_map('floatval', $diffs);

    // Calculate the new differential
    $new_diff = ($gross - (float)$tee->course_rating - $pcc) * (113 / (float)$tee->slope_rating);
    $new_diff = round($new_diff, 1);

    // Simulate: prepend new round, cap at 20
    $simulated = array_slice(array_merge([$new_diff], $diffs), 0, 20);
    $count     = count($simulated);

    if ($count < 3) {
        wp_send_json_error(['message' => 'Not enough rounds to calculate (minimum 3 needed).']);
    }

    // WHS table: number of rounds → best N to use
    $whs_table = [
        3 => 1, 4 => 1, 5 => 1,
        6 => 2, 7 => 2, 8 => 2,
        9 => 3, 10 => 3, 11 => 3,
        12 => 4, 13 => 4, 14 => 4,
        15 => 5, 16 => 5,
        17 => 6, 18 => 6,
        19 => 7, 20 => 8,
    ];
    $use_n = $whs_table[min($count, 20)] ?? 8;

    sort($simulated);
    $best   = array_slice($simulated, 0, $use_n);
    $new_hi = round((array_sum($best) / count($best)) * 0.96, 1);
    $new_hi = min(max($new_hi, 0.0), 54.0);

    // Playing handicap helper — mirrors view_playing_handicaps exactly
    $play_hcp = function($hi, $tee_data) {
        $exact = $hi * ($tee_data->slope_rating / 113) + ($tee_data->course_rating - $tee_data->par);
        return (int) round($exact * 0.95);
    };

    $cur_play = [];
    $new_play = [];
    foreach (['White', 'Yellow', 'Black'] as $colour) {
        if (!isset($tees_by_colour[$colour])) continue;
        $key            = strtolower($colour);
        $cur_play[$key] = $play_hcp($cur_hi, $tees_by_colour[$colour]);
        $new_play[$key] = $play_hcp($new_hi, $tees_by_colour[$colour]);
    }

    wp_send_json_success([
        'new_diff'  => $new_diff,
        'cur_hi'    => number_format($cur_hi, 1),
        'new_hi'    => number_format($new_hi, 1),
        'hi_change' => round($new_hi - $cur_hi, 1),
        'cur_play'  => $cur_play,
        'new_play'  => $new_play,
    ]);
}
