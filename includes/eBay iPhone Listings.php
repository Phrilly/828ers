<?php
/**
 * eBay iPhone Listings
 * Shortcode: [ebay_iphone_listings]
 */

if ( ! defined( 'ABSPATH' ) ) exit;

add_shortcode( 'ebay_iphone_listings', function ( $atts ) {
    $atts = shortcode_atts([
        'query'  => 'iPhone',
        'limit'  => 6,
        'market' => 'EBAY_GB',
    ], $atts );

    $client_id     = defined('EBAY_CLIENT_ID')     ? EBAY_CLIENT_ID     : '';
    $client_secret = defined('EBAY_CLIENT_SECRET') ? EBAY_CLIENT_SECRET : '';

    if ( empty($client_id) || empty($client_secret) ) {
        return '<p class="ebay-error">eBay API credentials not configured.</p>';
    }

    // Step 1: Get token
    $token_response = wp_remote_post( 'https://api.ebay.com/identity/v1/oauth2/token', [
        'headers' => [
            'Authorization' => 'Basic ' . base64_encode( $client_id . ':' . $client_secret ),
            'Content-Type'  => 'application/x-www-form-urlencoded',
        ],
        'body'    => 'grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope',
        'timeout' => 15,
    ] );

    if ( is_wp_error( $token_response ) ) {
        return '<p class="ebay-error">eBay token request failed: ' . esc_html( $token_response->get_error_message() ) . '</p>';
    }

    $token_body = json_decode( wp_remote_retrieve_body( $token_response ), true );
    $token      = $token_body['access_token'] ?? '';

    if ( empty( $token ) ) {
        return '<p class="ebay-error">eBay token empty. Response: ' . esc_html( wp_remote_retrieve_body( $token_response ) ) . '</p>';
    }

    // Step 2: Search listings
    $search_url = 'https://api.ebay.com/buy/browse/v1/item_summary/search?' . http_build_query([
        'q'     => $atts['query'],
        'limit' => (int) $atts['limit'],
        'sort'  => 'bestMatch',
    ]);

    $search_response = wp_remote_get( $search_url, [
        'headers' => [
            'Authorization'           => 'Bearer ' . $token,
            'X-EBAY-C-MARKETPLACE-ID' => $atts['market'],
            'Content-Type'            => 'application/json',
        ],
        'timeout' => 15,
    ] );

    if ( is_wp_error( $search_response ) ) {
        return '<p class="ebay-error">eBay search failed: ' . esc_html( $search_response->get_error_message() ) . '</p>';
    }

    $search_body = json_decode( wp_remote_retrieve_body( $search_response ), true );
    $items       = $search_body['itemSummaries'] ?? [];

    if ( empty( $items ) ) {
        return '<p class="ebay-error">No listings found. Raw: ' . esc_html( wp_remote_retrieve_body( $search_response ) ) . '</p>';
    }

    // Step 3: Render
    ob_start(); ?>
    <div class="ebay-listings-grid">
        <?php foreach ( $items as $item ) :
            $title    = esc_html( $item['title'] ?? '' );
            $price    = esc_html( $item['price']['value'] ?? 'N/A' );
            $currency = esc_html( $item['price']['currency'] ?? '' );
            $image    = esc_url( $item['image']['imageUrl'] ?? '' );
            $url      = esc_url( $item['itemWebUrl'] ?? '#' );
            $cond     = esc_html( $item['condition'] ?? '' );
        ?>
        <div class="ebay-listing-card">
            <a href="<?php echo $url; ?>" target="_blank" rel="noopener noreferrer">
                <img src="<?php echo $image; ?>" alt="<?php echo $title; ?>" loading="lazy" />
            </a>
            <div class="ebay-listing-info">
                <p class="ebay-listing-title">
                    <a href="<?php echo $url; ?>" target="_blank" rel="noopener noreferrer"><?php echo $title; ?></a>
                </p>
                <?php if ( $cond ) : ?>
                    <span class="ebay-listing-condition"><?php echo $cond; ?></span>
                <?php endif; ?>
                <p class="ebay-listing-price"><?php echo $currency . ' ' . $price; ?></p>
                <a class="ebay-listing-btn" href="<?php echo $url; ?>" target="_blank" rel="noopener noreferrer">View on eBay</a>
            </div>
        </div>
        <?php endforeach; ?>
    </div>
    <?php
    return ob_get_clean();
} );