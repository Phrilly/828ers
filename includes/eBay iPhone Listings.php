<?php
/**
 * eBay iPhone Listings
 * Shortcode: [ebay_iphone_listings]
 */

$client_id     = defined('EBAY_CLIENT_ID')     ? EBAY_CLIENT_ID     : '';
$client_secret = defined('EBAY_CLIENT_SECRET') ? EBAY_CLIENT_SECRET : '';

if ( ! defined( 'ABSPATH' ) ) exit;

add_shortcode( 'ebay_iphone_listings', function ( $atts ) {
    $atts = shortcode_atts([
        'query'  => 'iPhone',
        'limit'  => 6,
        'market' => 'EBAY_GB',
    ], $atts );

    $client_id     = 'YOUR_APP_ID_HERE';
    $client_secret = 'YOUR_CERT_ID_HERE';

    $token = ebay_iphone_get_token( $client_id, $client_secret );
    if ( ! $token ) {
        return '<p class="ebay-error">eBay listings unavailable right now.</p>';
    }

    $items = ebay_iphone_fetch( $token, $atts['query'], (int) $atts['limit'], $atts['market'] );
    if ( ! $items ) {
        return '<p class="ebay-error">No listings found.</p>';
    }

    return ebay_iphone_render( $items );
} );

function ebay_iphone_get_token( $client_id, $client_secret ) {
    $response = wp_remote_post( 'https://api.ebay.com/identity/v1/oauth2/token', [
        'headers' => [
            'Authorization' => 'Basic ' . base64_encode( $client_id . ':' . $client_secret ),
            'Content-Type'  => 'application/x-www-form-urlencoded',
        ],
        'body'    => 'grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope',
        'timeout' => 10,
    ] );

    if ( is_wp_error( $response ) ) return false;
    $data = json_decode( wp_remote_retrieve_body( $response ), true );
    return $data['access_token'] ?? false;
}

function ebay_iphone_fetch( $token, $query, $limit, $market ) {
    $url = 'https://api.ebay.com/buy/browse/v1/item_summary/search?' . http_build_query([
        'q'     => $query,
        'limit' => $limit,
        'sort'  => 'bestMatch',
    ]);

    $response = wp_remote_get( $url, [
        'headers' => [
            'Authorization'           => 'Bearer ' . $token,
            'X-EBAY-C-MARKETPLACE-ID' => $market,
            'Content-Type'            => 'application/json',
        ],
        'timeout' => 10,
    ] );

    if ( is_wp_error( $response ) ) return false;
    $data = json_decode( wp_remote_retrieve_body( $response ), true );
    return $data['itemSummaries'] ?? false;
}

function ebay_iphone_render( $items ) {
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
}