<?php
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * 1. The Javascript Listener
 * Waits for the user to click the Divi button with the ID "rebuild-history-btn"
 */
add_action('wp_footer', function() {
    ?>
    <script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        // Target the exact CSS ID you set in the Divi Builder
        const trigger = document.getElementById('rebuild-history-btn');

        if (trigger) {
            trigger.addEventListener('click', function(e) {
                e.preventDefault(); 
                
                // Safety check
                if (!confirm('Rebuild WHS History for all players? This takes a few seconds.')) {
                    return;
                }

                // Change the Divi button text to show it's working
                const originalText = trigger.innerText;
                trigger.innerText = '⏳ Rebuilding...';
                trigger.style.pointerEvents = 'none';
                trigger.style.opacity = '0.7';

                const ajaxUrl = typeof GolfMasterAjax !== 'undefined' ? GolfMasterAjax.ajaxUrl : '<?php echo admin_url('admin-ajax.php'); ?>';
                const nonce = '<?php echo wp_create_nonce('golf_rebuild_nonce'); ?>';

                const formData = new URLSearchParams();
                formData.append('action', 'golf_execute_visible_rebuild');
                formData.append('nonce', nonce);

                // Send the request to the backend PHP function
                fetch(ajaxUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        alert('Success: ' + data.data);
                        location.reload(); 
                    } else {
                        alert('Error: ' + data.data);
                        trigger.innerText = originalText;
                        trigger.style.pointerEvents = 'auto';
                        trigger.style.opacity = '1';
                    }
                })
                .catch(err => {
                    alert('A network error occurred while rebuilding.');
                    trigger.innerText = originalText;
                    trigger.style.pointerEvents = 'auto';
                    trigger.style.opacity = '1';
                });
            });
        }
    });
    </script>
    <?php
});

/**
 * 2. The AJAX Handler (The PHP Backend)
 * Executes the stored procedure safely.
 */
add_action('wp_ajax_golf_execute_visible_rebuild', 'golf_handle_visible_rebuild');
add_action('wp_ajax_nopriv_golf_execute_visible_rebuild', 'golf_handle_visible_rebuild');

function golf_handle_visible_rebuild() {
    // Security check
    check_ajax_referer('golf_rebuild_nonce', 'nonce');

    global $wpdb;

    // Execute the stored procedure
    $result = $wpdb->query("CALL sp_rebuild_all_players()");

    if ($result !== false) {
        wp_send_json_success('WHS History successfully rebuilt.');
    } else {
        wp_send_json_error('Database error: ' . $wpdb->last_error);
    }
    
    wp_die();
}