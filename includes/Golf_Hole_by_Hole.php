<?php
/**
 * Hole By Hole Analysis Dashboard
 * Shortcode: [Golf_Hole_by_Hole]
 * AJAX action: gh_load_hbh_analysis
 */

if ( ! defined( 'ABSPATH' ) ) exit;

add_shortcode('Golf_Hole_by_Hole', function ($atts) {
    global $wpdb;

    // Get players
    $players = $wpdb->get_results("SELECT player_id, name FROM {$wpdb->prefix}golf_players ORDER BY name ASC");
    
    // Get ALL courses
    $courses = $wpdb->get_results("
        SELECT course_id, course_name 
        FROM {$wpdb->prefix}golf_courses 
        ORDER BY course_name ASC
    ");

    $nonce = wp_create_nonce('gh_hbh_nonce');

    ob_start();
    ?>
    <div id="gh-hbh-app">
        <div class="history-filter-bar">
            <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
                <div>
                    <label for="hbh-player">Player:</label>
                    <select id="hbh-player" class="gh-select">
                        <option value="0">-- All Players --</option>
                        <?php foreach ($players as $p): ?>
                            <option value="<?php echo (int)$p->player_id; ?>"><?php echo esc_html($p->name); ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div>
                    <label for="hbh-course">Course:</label>
                    <select id="hbh-course" class="gh-select">
                        <option value="0">-- Select a Course --</option>
                        <?php foreach ($courses as $c): ?>
                            <?php 
                                // Auto-select Ramsey if it exists in the list
                                $is_ramsey = (stripos($c->course_name, 'Ramsey') !== false); 
                                $selected_attr = $is_ramsey ? 'selected="selected"' : '';
                            ?>
                            <option value="<?php echo (int)$c->course_id; ?>" <?php echo $selected_attr; ?>>
                                <?php echo esc_html($c->course_name); ?>
                            </option>
                        <?php endforeach; ?>
                    </select>
                </div>
            </div>
        </div>

        <div id="hbh-loading" style="display:none; text-align:center; padding: 40px; color:#666; font-style:italic;">
            Loading Hole Analysis...
        </div>

        <div id="hbh-results-container">
            <div style="text-align:center; padding:40px; color:#888; border: 2px dashed #ddd; border-radius: 8px;">
                Select a course above to load hole-by-hole analytics.
            </div>
        </div>
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const playerSelect = document.getElementById('hbh-player');
        const courseSelect = document.getElementById('hbh-course');
        const loadingDiv = document.getElementById('hbh-loading');
        const resultsContainer = document.getElementById('hbh-results-container');

        function fetchAnalysis() {
            const playerId = playerSelect.value;
            const courseId = courseSelect.value;

            if (courseId == 0) return;

            resultsContainer.style.display = 'none';
            loadingDiv.style.display = 'block';

            const formData = new URLSearchParams();
            formData.append('action', 'gh_load_hbh_analysis');
            formData.append('player_id', playerId);
            formData.append('course_id', courseId);
            formData.append('security', '<?php echo esc_js($nonce); ?>');

            fetch('<?php echo esc_url(admin_url('admin-ajax.php')); ?>', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                loadingDiv.style.display = 'none';
                resultsContainer.style.display = 'block';
                if(data.success) {
                    resultsContainer.innerHTML = data.data;
                } else {
                    resultsContainer.innerHTML = `<div style="color:#d63638; text-align:center; padding:20px;">${data.data}</div>`;
                }
            })
            .catch(err => {
                loadingDiv.style.display = 'none';
                resultsContainer.style.display = 'block';
                resultsContainer.innerHTML = `<div style="color:#d63638; text-align:center; padding:20px;">An error occurred.</div>`;
            });
        }

        playerSelect.addEventListener('change', fetchAnalysis);
        courseSelect.addEventListener('change', fetchAnalysis);

        // Auto-load the dashboard immediately if a course is selected by default
        if (courseSelect.value && courseSelect.value !== "0") {
            fetchAnalysis();
        }

        // Client-side table sorting listener (Bulletproof Arrow Injection)
        document.addEventListener('click', function(e) {
            const th = e.target.closest('th.sortable');
            if (!th) return;

            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const index = Array.from(th.parentNode.children).indexOf(th);
            
            // Determine sort direction
            let asc = !th.classList.contains('asc');
            
            // Reset all headers and set arrows back to default
            table.querySelectorAll('th.sortable').forEach(h => {
                h.classList.remove('asc', 'desc');
                const icon = h.querySelector('.sort-icon');
                if(icon) {
                    icon.innerHTML = '↕';
                    icon.style.color = '#ccc';
                }
            });
            
            // Apply new direction and arrow to clicked header
            th.classList.add(asc ? 'asc' : 'desc');
            const activeIcon = th.querySelector('.sort-icon');
            if(activeIcon) {
                activeIcon.innerHTML = asc ? '▲' : '▼';
                activeIcon.style.color = '#137a3d';
            }

            rows.sort((a, b) => {
                // Strip everything except numbers, decimals, and minus signs
                let valA = parseFloat(a.children[index].innerText.replace(/[^0-9.-]+/g, ''));
                let valB = parseFloat(b.children[index].innerText.replace(/[^0-9.-]+/g, ''));
                
                // Push N/A or blanks to the bottom
                if (isNaN(valA)) valA = asc ? 9999 : -9999;
                if (isNaN(valB)) valB = asc ? 9999 : -9999;

                return asc ? valA - valB : valB - valA;
            });

            // Re-append sorted rows
            tbody.append(...rows);
        });
    });
    </script>
    <?php
    return ob_get_clean();
});


add_action('wp_ajax_gh_load_hbh_analysis', 'gh_load_hbh_analysis');
add_action('wp_ajax_nopriv_gh_load_hbh_analysis', 'gh_load_hbh_analysis');

function gh_load_hbh_analysis() {
    check_ajax_referer('gh_hbh_nonce', 'security');
    global $wpdb;

    $player_id = (int)$_POST['player_id'];
    $course_id = (int)$_POST['course_id'];

    if (!$course_id) {
        wp_send_json_error("Invalid selection.");
    }

    $sql = "SELECT * FROM view_golf_hole_analysis WHERE player_id = %d AND course_id = %d ORDER BY hole_number ASC";
    $results = $wpdb->get_results($wpdb->prepare($sql, $player_id, $course_id), ARRAY_A);

    if (!$results || count($results) === 0) {
        wp_send_json_error("No hole-by-hole data found for this selection.");
    }

    // Extract Summary Variables
    $max_played = 0;
    $hardest_hole = 0;
    $easiest_hole = 0;
    
    foreach($results as $r) {
        if ($r['times_played'] > $max_played) $max_played = $r['times_played'];
        if ($r['actual_difficulty_rank'] == 1) $hardest_hole = $r['hole_number'];
        if ($r['actual_difficulty_rank'] == count($results)) $easiest_hole = $r['hole_number'];
    }

    ob_start();
    ?>
    
    <div class="hbh-summary-cards">
        <div class="hbh-card">
            <h4>Rounds Analysed</h4>
            <div class="hbh-val"><?php echo (int)$max_played; ?></div>
        </div>
        <div class="hbh-card">
            <h4>Hardest Hole</h4>
            <div class="hbh-val" style="color:#e74c3c;">Hole <?php echo $hardest_hole; ?></div>
        </div>
        <div class="hbh-card">
            <h4>Easiest Hole</h4>
            <div class="hbh-val" style="color:#2ecc71;">Hole <?php echo $easiest_hole; ?></div>
        </div>
    </div>

    <div class="history-scroll" style="margin-top: 20px;">
        <table class="history-table hbh-analysis-table">
            <thead>
                <tr>
                    <th class="tc sortable asc" style="cursor:pointer; user-select:none; white-space:nowrap;">Hole <span class="sort-icon" style="color:#137a3d; font-size:10px; margin-left:4px;">▲</span></th>
                    <th class="tc sortable" style="cursor:pointer; user-select:none; white-space:nowrap;">Par <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc sortable" style="cursor:pointer; user-select:none; white-space:nowrap;" title="Official Stroke Index">Card S.I. <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc sortable" style="cursor:pointer; user-select:none; white-space:nowrap;" title="True rank based on strokes over par">True Rank <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc sortable" style="cursor:pointer; user-select:none; white-space:nowrap;">Avg Score <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc sortable" style="cursor:pointer; user-select:none; white-space:nowrap;">To Par <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc sortable" style="cursor:pointer; user-select:none; white-space:nowrap;">Avg Pts <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc hbh-hide-mobile sortable" style="cursor:pointer; user-select:none; white-space:nowrap;" title="Standard Deviation (Variance)">Var (σ) <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc hbh-hide-mobile sortable" style="cursor:pointer; user-select:none; white-space:nowrap;">Best <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                    <th class="tc hbh-hide-mobile sortable" style="cursor:pointer; user-select:none; white-space:nowrap;">Worst <span class="sort-icon" style="color:#ccc; font-size:10px; margin-left:4px;">↕</span></th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($results as $r): 
                    $par = (int)$r['par'];
                    $avg = (float)$r['avg_gross'];
                    $to_par = (float)$r['avg_to_par'];
                    
                    $to_par_fmt = ($to_par > 0 ? '+' : '') . number_format($to_par, 2);
                    $to_par_class = $to_par > 0 ? 'color:#e74c3c;' : 'color:#2ecc71; font-weight:bold;';

                    $si_official = $r['official_si'] ? (int)$r['official_si'] : 0;
                    $si_actual = (int)$r['actual_difficulty_rank'];
                    
                    $rank_class = '';
                    if ($si_official > 0) {
                        if ($si_actual <= $si_official - 4) $rank_class = 'hbh-rank-harder'; 
                        if ($si_actual >= $si_official + 4) $rank_class = 'hbh-rank-easier'; 
                    }

                    $t = (int)$r['times_played'];
                    
                    $std_dev_display = $t >= 2 ? number_format((float)$r['std_dev'], 2) : 'N/A';
                ?>
                <tr>
                    <td class="tc"><strong><?php echo (int)$r['hole_number']; ?></strong></td>
                    <td class="tc"><?php echo $par; ?></td>
                    <td class="tc" style="color:#888;"><?php echo $si_official ? $si_official : '-'; ?></td>
                    <td class="tc"><span class="<?php echo $rank_class; ?>"><?php echo $si_actual; ?></span></td>
                    <td class="tc" style="font-weight:bold; font-size:14px;"><?php echo number_format($avg, 2); ?></td>
                    <td class="tc" style="<?php echo $to_par_class; ?>"><?php echo $to_par_fmt; ?></td>
                    <td class="tc" style="color:#137a3d; font-weight:bold;"><?php echo number_format((float)$r['avg_pts'], 1); ?></td>
                    <td class="tc hbh-hide-mobile" style="color:#666; font-style:italic;"><?php echo $std_dev_display; ?></td>
                    <td class="tc hbh-hide-mobile"><span class="hbh-ringer best"><?php echo (int)$r['best_score']; ?></span></td>
                    <td class="tc hbh-hide-mobile"><span class="hbh-ringer worst"><?php echo (int)$r['worst_score']; ?></span></td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>

    <?php
    wp_send_json_success(ob_get_clean());
}