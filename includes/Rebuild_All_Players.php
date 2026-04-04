<?php
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * 1. Inject the Rebuild Button as a Floating Action Button
 * Guaranteed to be visible, ignoring brittle text-matching.
 */
add_action('wp_footer', function() {
    ?>
    <style>
        .828ers-floating-rebuild {
            position: fixed;
            bottom: 25px;
            right: 25px;
            z-index: 999999;
            background-color: #0073aa;
            color: #ffffff;
            border: none;
            border-radius: 50px;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: 600;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: background-color 0.2s, transform 0.2s;
        }
        .828ers-floating-rebuild:hover {
            background-color: #005177;
            transform: scale(1.05);
        }
    </style>

    <button id="828ers-rebuild-trigger" class="828ers-floating-rebuild">
        &#x267B; Rebuild All Players
    </button>

    <script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        const trigger = document.getElementById('828ers-rebuild-trigger');

        if (trigger) {
            trigger.addEventListener('click', function(e) {
                e.preventDefault(); 
                
                // Simple confirmation so a stray tap doesn't freeze the phone
                if (!confirm('Rebuild WHS History for all players? This takes a few seconds.')) {
                    return;
                }

                const originalText = trigger.innerHTML;
                trigger.innerHTML = '⏳ Rebuilding...';
                trigger.style.pointerEvents = 'none';

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
                    }
                })
                .catch(err => {
                    alert('A network error occurred while rebuilding.');
                    trigger.innerHTML = originalText;
                    trigger.style.pointerEvents = 'auto';
                });
            });
        }
    });
    </script>
    <?php
});

/**
 * 2. The AJAX Handler
 * Accessible to everyone on the frontend (no login required)
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