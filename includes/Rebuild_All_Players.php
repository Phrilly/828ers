<?php
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * 1. Inject the Rebuild Button next to the "Historic Scores" Title
 */
add_action('wp_footer', function() {
    ?>
    <script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        // Hunt for the header containing the specific text
        const elements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, .card-header, .section-title, header, .panel-title');
        let targetHeader = null;

        for (let el of elements) {
            if (el.textContent.includes('Historic Scores') && el.children.length < 5) {
                targetHeader = el;
                break;
            }
        }

        if (targetHeader) {
            // Adjust the header layout so the button sits nicely on the right
            targetHeader.style.display = 'flex';
            targetHeader.style.alignItems = 'center';
            targetHeader.style.justifyContent = 'space-between';

            // Create the visible button
            const rebuildBtn = document.createElement('button');
            rebuildBtn.innerHTML = '&#x267B; Rebuild All Players';
            rebuildBtn.className = '828ers-rebuild-btn';
            
            // Translucent styling to blend nicely over the blue background
            rebuildBtn.style.cssText = 'background: rgba(255, 255, 255, 0.15); border: 1px solid rgba(255, 255, 255, 0.4); color: #fff; padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; cursor: pointer; margin-left: 15px; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';

            rebuildBtn.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Simple confirmation so a stray tap doesn't freeze the phone
                if (!confirm('Rebuild WHS History for all players? This takes a few seconds.')) {
                    return;
                }

                const originalText = rebuildBtn.innerHTML;
                rebuildBtn.innerHTML = '⏳ Rebuilding...';
                rebuildBtn.style.pointerEvents = 'none';
                rebuildBtn.style.opacity = '0.7';

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
                        rebuildBtn.innerHTML = originalText;
                        rebuildBtn.style.pointerEvents = 'auto';
                        rebuildBtn.style.opacity = '1';
                    }
                })
                .catch(err => {
                    alert('A network error occurred while rebuilding.');
                    rebuildBtn.innerHTML = originalText;
                    rebuildBtn.style.pointerEvents = 'auto';
                    rebuildBtn.style.opacity = '1';
                });
            });

            targetHeader.appendChild(rebuildBtn);
        }
    });
    </script>
    <?php
});

/**
 * 2. The AJAX Handler
 * Accessible to everyone (no login required)
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