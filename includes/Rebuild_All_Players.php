<?php
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * 1. Inject the Rebuild Button (Aggressive Search + Fallback)
 */
add_action('wp_footer', function() {
    ?>
    <script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        let attempts = 0;
        
        // Use an interval to check for the header in case it loads slightly delayed
        const finder = setInterval(function() {
            attempts++;
            const elements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, div');
            let targetHeader = null;

            for (let el of elements) {
                // Match case-insensitive "historic scores", checking header tags or classes
                if ((el.tagName.match(/^H[1-6]$/i) || el.className.includes('header') || el.className.includes('title')) &&
                    el.textContent.toLowerCase().includes('historic scores') && el.children.length < 5) {
                    targetHeader = el;
                    break;
                }
            }

            if (targetHeader) {
                clearInterval(finder);
                
                // Prevent duplicate buttons if script runs twice
                if(targetHeader.querySelector('.828ers-rebuild-btn')) return;

                targetHeader.style.display = 'flex';
                targetHeader.style.alignItems = 'center';
                targetHeader.style.justifyContent = 'space-between';

                const rebuildBtn = document.createElement('button');
                rebuildBtn.innerHTML = '&#x267B; Rebuild All Players';
                rebuildBtn.className = '828ers-rebuild-btn';
                rebuildBtn.style.cssText = 'background: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.5); color: inherit; padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; cursor: pointer; margin-left: 15px; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';

                rebuildBtn.addEventListener('click', handleRebuildClick);
                targetHeader.appendChild(rebuildBtn);
                
            } else if (attempts > 10) {
                // If we check 10 times (5 seconds) and find nothing, inject a fallback floating button
                clearInterval(finder);
                console.log("828ers: 'Historic Scores' header not found. Injecting fallback button.");
                
                const fallbackBtn = document.createElement('button');
                fallbackBtn.innerHTML = '&#x267B; Rebuild All Players';
                fallbackBtn.className = '828ers-rebuild-btn';
                fallbackBtn.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: #0073aa; color: #fff; padding: 10px 15px; border-radius: 5px; border: none; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.3); cursor: pointer;';
                
                fallbackBtn.addEventListener('click', handleRebuildClick);
                document.body.appendChild(fallbackBtn);
            }
        }, 500);

        function handleRebuildClick(e) {
            e.preventDefault();
            const btn = e.target;
            
            if (!confirm('Rebuild WHS History for all players? This takes a few seconds.')) {
                return;
            }

            const originalText = btn.innerHTML;
            btn.innerHTML = '⏳ Rebuilding...';
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.7';

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
                    btn.innerHTML = originalText;
                    btn.style.pointerEvents = 'auto';
                    btn.style.opacity = '1';
                }
            })
            .catch(err => {
                alert('A network error occurred while rebuilding.');
                btn.innerHTML = originalText;
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            });
        }
    });
    </script>
    <?php
});

/**
 * 2. The AJAX Handler
 */
add_action('wp_ajax_golf_execute_visible_rebuild', 'golf_handle_visible_rebuild');
add_action('wp_ajax_nopriv_golf_execute_visible_rebuild', 'golf_handle_visible_rebuild');

function golf_handle_visible_rebuild() {
    check_ajax_referer('golf_rebuild_nonce', 'nonce');

    global $wpdb;

    $result = $wpdb->query("CALL sp_rebuild_all_players()");

    if ($result !== false) {
        wp_send_json_success('WHS History successfully rebuilt.');
    } else {
        wp_send_json_error('Database error: ' . $wpdb->last_error);
    }
    
    wp_die();
}