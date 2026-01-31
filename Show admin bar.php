add_filter('show_admin_bar', function ($show) {
    return current_user_can('manage_options') ? $show : false;
}, 10, 1);
