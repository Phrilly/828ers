<?php
/**
 * Golf Eclectic
 * Shortcode: [golf_eclectic]
 */

if ( ! defined( 'ABSPATH' ) ) exit;

add_shortcode( 'golf_eclectic', function () {
    global $wpdb;

    // ── Player order ──────────────────────────────────────────
    $ordered_names = ['Phil D', 'Phil B', 'Jay', 'Adder'];

    // Get all players, then sort to match required order
    $all_players = $wpdb->get_results(
        "SELECT player_id, name FROM wp_golf_players ORDER BY name ASC"
    );

    // Build ordered player list — only include players in our list
    $players = [];
    foreach ( $ordered_names as $ordered_name ) {
        foreach ( $all_players as $p ) {
            if ( trim( $p->name ) === $ordered_name ) {
                $players[] = $p;
                break;
            }
        }
    }

    // ── Available months (only months that have data) ─────────
    $months_raw = $wpdb->get_results(
        "SELECT DISTINCT
            MONTH(s.date_played) AS month_num,
            YEAR(s.date_played)  AS year_num
         FROM wp_golf_scores s
         JOIN wp_golf_tees t   ON s.tee_id    = t.tee_id
         JOIN wp_golf_courses c ON t.course_id = c.course_id
         WHERE s.is_excluded = 0
           AND c.course_name = 'Ramsey Golf Club'
         ORDER BY year_num DESC, month_num DESC"
    );

    if ( empty( $months_raw ) ) {
        return '<p>No eclectic data available.</p>';
    }

    // ── Selected month/year ───────────────────────────────────
    $selected_month = isset( $_GET['ecl_month'] ) ? (int) $_GET['ecl_month'] : (int) $months_raw[0]->month_num;
    $selected_year  = isset( $_GET['ecl_year'] )  ? (int) $_GET['ecl_year']  : (int) $months_raw[0]->year_num;

    // ── Fetch eclectic data ───────────────────────────────────
    $rows = $wpdb->get_results( $wpdb->prepare(
        "SELECT
            player_id,
            player_name,
            hole_number,
            par,
            best_gross,
            best_stableford
         FROM view_eclectic
         WHERE month_num = %d
           AND year_num  = %d
         ORDER BY hole_number ASC",
        $selected_month,
        $selected_year
    ) );

    // ── Index data: [player_id][hole_number] = row ────────────
    $data = [];
    foreach ( $rows as $row ) {
        $data[ $row->player_id ][ (int) $row->hole_number ] = $row;
    }

    // ── Par per hole ──────────────────────────────────────────
    $hole_pars = $wpdb->get_results(
        "SELECT DISTINCT h.hole_number, h.par
         FROM wp_golf_holes h
         JOIN wp_golf_tees t    ON h.tee_id    = t.tee_id
         JOIN wp_golf_courses c ON t.course_id = c.course_id
         WHERE c.course_name = 'Ramsey Golf Club'
         ORDER BY h.hole_number ASC"
    );

    // Month name helper
    $month_names = [
        1=>'January',2=>'February',3=>'March',4=>'April',
        5=>'May',6=>'June',7=>'July',8=>'August',
        9=>'September',10=>'October',11=>'November',12=>'December'
    ];

    // Current page URL for form action
    $page_url = get_permalink();

    ob_start();
    ?>
    <div class="eclectic-wrap">

        <?php // ── Month/Year selector ──────────────────────────── ?>
        <form class="eclectic-filter" method="GET" action="<?php echo esc_url( $page_url ); ?>">
            <label for="ecl-period">Period:</label>
            <select id="ecl-period" name="ecl_month" onchange="this.form.submit()">
                <?php foreach ( $months_raw as $m ) :
                    $selected = ( (int)$m->month_num === $selected_month && (int)$m->year_num === $selected_year ) ? 'selected' : '';
                ?>
                    <option value="<?php echo (int)$m->month_num; ?>"
                            data-year="<?php echo (int)$m->year_num; ?>"
                            <?php echo $selected; ?>>
                        <?php echo esc_html( $month_names[ (int)$m->month_num ] . ' ' . $m->year_num ); ?>
                    </option>
                <?php endforeach; ?>
            </select>
            <input type="hidden" name="ecl_year" id="ecl-year" value="<?php echo $selected_year; ?>">
        </form>

        <script>
        document.getElementById('ecl-period').addEventListener('change', function() {
            var opt = this.options[this.selectedIndex];
            document.getElementById('ecl-year').value = opt.getAttribute('data-year');
            this.form.submit();
        });
        </script>

        <h3 class="eclectic-title">
            Eclectic — <?php echo esc_html( $month_names[$selected_month] . ' ' . $selected_year ); ?>
        </h3>

        <div class="eclectic-scroll">
        <table class="eclectic-table">
            <thead>
                <tr class="eclectic-header-top">
                    <th class="ecl-hole-col">Hole</th>
                    <th class="ecl-par-col">Par</th>
                    <?php foreach ( $players as $p ) : ?>
                        <th class="ecl-player-col" colspan="2">
                            <?php echo esc_html( $p->name ); ?>
                        </th>
                    <?php endforeach; ?>
                </tr>
                <tr class="eclectic-header-sub">
                    <th></th>
                    <th></th>
                    <?php foreach ( $players as $p ) : ?>
                        <th class="ecl-sub">Gross</th>
                        <th class="ecl-sub">Stbf</th>
                    <?php endforeach; ?>
                </tr>
            </thead>
            <tbody>
                <?php
                $totals_gross = array_fill_keys( array_column( $players, 'player_id' ), 0 );
                $totals_stbf  = array_fill_keys( array_column( $players, 'player_id' ), 0 );

                foreach ( $hole_pars as $hole ) :
                    $hole_num = (int) $hole->hole_number;
                    $par      = (int) $hole->par;
                    $row_class = ( $hole_num % 2 === 0 ) ? 'ecl-row-even' : 'ecl-row-odd';

                    // Separator after hole 9
                    if ( $hole_num === 10 ) : ?>
                        <tr class="ecl-turn-row">
                            <td colspan="<?php echo 2 + ( count($players) * 2 ); ?>">— Turn —</td>
                        </tr>
                    <?php endif; ?>

                    <tr class="<?php echo $row_class; ?>">
                        <td class="ecl-hole-num"><?php echo $hole_num; ?></td>
                        <td class="ecl-par"><?php echo $par; ?></td>

                        <?php foreach ( $players as $p ) :
                            $pid   = $p->player_id;
                            $d     = $data[$pid][$hole_num] ?? null;

                            if ( $d ) :
                                $gross = (int) $d->best_gross;
                                $stbf  = (int) $d->best_stableford;
                                $totals_gross[$pid] += $gross;
                                $totals_stbf[$pid]  += $stbf;

                                // Gross score class vs par
                                $diff = $gross - $par;
                                if     ( $diff <= -2 ) $gross_class = 'ecl-eagle';
                                elseif ( $diff === -1 ) $gross_class = 'ecl-birdie';
                                elseif ( $diff === 0  ) $gross_class = 'ecl-par';
                                elseif ( $diff === 1  ) $gross_class = 'ecl-bogey';
                                else                    $gross_class = 'ecl-double';

                                // Stableford class
                                if     ( $stbf >= 4 ) $stbf_class = 'ecl-stbf-great';
                                elseif ( $stbf === 3 ) $stbf_class = 'ecl-stbf-good';
                                elseif ( $stbf === 2 ) $stbf_class = 'ecl-stbf-par';
                                elseif ( $stbf === 1 ) $stbf_class = 'ecl-stbf-poor';
                                else                   $stbf_class = 'ecl-stbf-zero';
                            ?>
                                <td class="ecl-score ecl-gross">
                                    <span class="ecl-circle <?php echo $gross_class; ?>"><?php echo $gross; ?></span>
                                </td>
                                <td class="ecl-score ecl-stbf">
                                    <span class="ecl-stbf-val <?php echo $stbf_class; ?>"><?php echo $stbf; ?></span>
                                </td>
                            <?php else : ?>
                                <td class="ecl-score ecl-gross"><span class="ecl-no-score">•</span></td>
                                <td class="ecl-score ecl-stbf"><span class="ecl-stbf-val ecl-stbf-zero">0</span></td>
                            <?php endif; ?>

                        <?php endforeach; ?>
                    </tr>

                <?php endforeach; ?>
            </tbody>
            <tfoot>
                <tr class="ecl-totals-row">
                    <td class="ecl-hole-num"><strong>Total</strong></td>
                    <td class="ecl-par"></td>
                    <?php foreach ( $players as $p ) : ?>
                        <td class="ecl-score ecl-gross"><strong><?php echo $totals_gross[$p->player_id]; ?></strong></td>
                        <td class="ecl-score ecl-stbf"><strong><?php echo $totals_stbf[$p->player_id]; ?></strong></td>
                    <?php endforeach; ?>
                </tr>
            </tfoot>
        </table>
        </div>

    </div>
    <?php
    return ob_get_clean();
} );