<?php
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * 1. Create the Shortcode [828ers_rebuild]
 * You can place this anywhere in Divi (Text Module, Code Module, etc.)
 */
add_shortcode('828ers_rebuild', function() {
    ob_start();
    ?>
    <a href="#" id="828ers-rebuild-trigger" style="color: #ffffff; font-size: 14px; text-decoration: underline; cursor: pointer; font-weight: bold;">
        &#x267B; Rebuild All Players
    </a>

    <script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        const trigger = document.getElementById('828ers-rebuild-trigger');

        if (trigger) {
            trigger.addEventListener('click', function(e) {
                e.preventDefault(); 
                
                if (!confirm('Rebuild WHS History for all players? This takes a few seconds.')) {
                    return;
                }

                const originalText = trigger.innerHTML;
                trigger.innerHTML = '⏳ Rebuilding...';
                trigger.style.pointerEvents = 'none';
                trigger.style.opacity = '0.7';

                const ajaxUrl = typeof GolfMasterAjax !== 'undefined' ? GolfMasterAjax.ajaxUrl : '<?php echo admin_url('admin-ajax.php'); ?>';
                const nonce = '<?php echo wp_create_nonce('golf_rebuild_nonce'); ?>';

                const formData = new URLSearchParams();
                formData.append('action', 'golf_execute_visible_rebuild');
                formData.append('nonce', nonce);

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
                        trigger.innerHTML = originalText;
                        trigger.style.pointerEvents = 'auto';
                        trigger.style.opacity = '1';
                    }
                })
                .catch(err => {
                    alert('A network error occurred while rebuilding.');
                    trigger.innerHTML = originalText;
                    trigger.style.pointerEvents = 'auto';
                    trigger.style.opacity = '1';
                });
            });
        }
    });
    </script>
    <?php
    return ob_get_clean();
});

/**
 * 2. The AJAX Handler
 * Executes the stored procedure safely in the background.
 */
add_action('wp_ajax_golf_execute_visible_rebuild', 'golf_handle_visible_rebuild');
add_action('wp_ajax_nopriv_golf_execute_visible_rebuild', 'golf_handle_visible_rebuild');

function golf_handle_visible_rebuild() {
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