# shop/urls.py
from django.urls import path

# import module-level, KHÔNG import rồi lại định nghĩa trùng tên trong file này
from .views import (
    home,                    # module views/home.py
    sanpham as sanpham_ui,   # module views/sanpham.py (UI khách)
    danh_muc_view as dm,     # module views/danh_muc_view.py
    admin_view as av,        # module views/admin_view.py
    taikhoan_view as tv,     # module views/taikhoan_view.py (API auth)
    auth_pages as ap,        # module views/auth_pages.py (UI login/register)
    giohang as cart_ui,      # module views/giohang.py (UI giỏ hàng)
    giohang_api as cart,     # module views/giohang_api.py (API giỏ hàng)
    sanpham_view as spv,     # module views/sanpham_view.py (API + Admin SP)
    donhang,                 # module views/donhang.py (UI/flow đơn hàng)
    donhang_view as dv,      # module views/donhang_view.py (API đơn hàng)
)

app_name = "shop"

urlpatterns = [
    # --------- Trang khách ---------
    path("",                     home.home,                 name="home"),
    path("sanpham/",             sanpham_ui.sanpham_list,   name="sanpham_list"),
    path("sanpham/category/<str:cat_id>/", sanpham_ui.product_by_category, name="product_by_category"),
    path("sanpham/<str:sp_id>/", sanpham_ui.product_detail, name="product_detail"),

    path("cart/",                cart_ui.view_cart,         name="view_cart"),

    path("checkout/",            donhang.checkout_view,     name="checkout"),
    path("orders/",              donhang.orders_index,      name="orders_index"),
    path("orders/<str:order_id>/", donhang.order_details,   name="order_details"),
    path("orders/cancel/",       donhang.cancel_order,      name="cancel_order"),
    path("orders/place/",        donhang.place_order,       name="place_order"),

    # --------- Danh mục ---------
    path("danh-muc/",                    dm.list_danh_muc,   name="danh_muc_list"),
    path("danh-muc/create/",             dm.create_danh_muc, name="danh_muc_create"),
    path("danh-muc/update/<str:id>/",    dm.update_danh_muc, name="danh_muc_update"),
    path("danh-muc/delete/<str:id>/",    dm.delete_danh_muc, name="danh_muc_delete"),

    # --------- ✅ API Sản phẩm ---------
    path("api/products/",                spv.products_list,  name="api_products_list"),
    path("api/products/create/",         spv.products_create, name="api_products_create"),
    path("api/products/<str:id>/",       spv.product_detail, name="api_product_detail"),

    # --------- API Đơn hàng ---------
    path("api/orders/",                  dv.orders_list,     name="api_orders_list"),
    path("api/orders/create/",           dv.order_create,    name="api_order_create"),
    path("api/orders/<str:id>/",         dv.order_detail,    name="api_order_detail"),

    # --------- ✅ API Giỏ hàng (khớp template JS) ---------
    path("api/cart/add/<str:sp_id>/",    cart.api_add_to_cart, name="api_add_to_cart"),
    path("api/cart/badge/",              cart.api_cart_badge,  name="api_cart_badge"),
    path("api/cart/list/",               cart.api_cart_list,   name="api_cart_list"),
    path("api/cart/update/<str:sp_id>/", cart.api_cart_update, name="api_cart_update"),
    path("api/cart/remove/<str:sp_id>/", cart.api_cart_remove, name="api_cart_remove"),
    path("api/cart/clear/",              cart.api_cart_clear,  name="api_cart_clear"),

    # --------- Admin ---------
    path("admin-panel/",                 av.dashboard,        name="admin_dashboard"),
    path("admin-panel/dashboard/",       av.dashboard,        name="admin_dashboard2"),

    path("admin-panel/products/",               spv.admin_products_list, name="admin_products"),
    path("admin-panel/products/create/",        spv.product_create,      name="admin_product_create"),
    path("admin-panel/products/<str:id>/edit/", spv.product_edit,        name="admin_product_edit"),
    path("admin-panel/products/<str:id>/delete/", spv.product_delete,    name="admin_product_delete"),

    path("admin-panel/categories/",             av.categories_list,      name="admin_categories"),
    path("admin-panel/categories/create/",      av.category_create,      name="admin_category_create"),
    path("admin-panel/categories/<str:id>/edit/", av.category_edit,      name="admin_category_edit"),
    path("admin-panel/categories/<str:id>/delete/", av.category_delete,  name="admin_category_delete"),
        # --------- Admin Accounts ---------
    path("admin-panel/accounts/",                av.accounts_list,   name="admin_accounts"),
    path("admin-panel/accounts/create/",         av.account_create,  name="admin_account_create"),
    path("admin-panel/accounts/<str:id>/edit/",  av.account_edit,    name="admin_account_edit"),
    path("admin-panel/accounts/<str:id>/delete/",av.account_delete,  name="admin_account_delete"),
    # --------- Auth pages & APIs ---------
    path("auth/login/",    ap.login_page,    name="auth_login_page"),
    path("auth/register/", ap.register_page, name="auth_register_page"),
    path("auth/logout/",   ap.logout_view,   name="auth_logout_page"),

    path("api/auth/register", tv.auth_register),
    path("api/auth/login",    tv.auth_login),
    path("api/auth/logout",   tv.auth_logout),
    path("api/auth/me",       tv.auth_me),
]
