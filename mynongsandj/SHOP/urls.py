from django.urls import path
from .views import danh_muc_view as dm
from .views import sanpham as sanpham
from .views import home, admin_view as av
from .views import taikhoan_view as tv
from .views import auth_pages as ap

from .views import giohang as giohang
# from .views import giohang_view as ghv
from .views import sanpham_view as spv
from .views import donhang, donhang_view as dv
app_name = "shop"

urlpatterns = [
    path("", home.home, name="home"),
    path("sanpham/", sanpham.sanpham_list, name="sanpham_list"),
    path("sanpham/category/<str:cat_id>/", sanpham.product_by_category, name="product_by_category"),
    path("sanpham/<str:sp_id>/", sanpham.product_detail, name="product_detail"),

    # path("sanpham/add/<str:sp_id>/", sanpham.add_to_cart, name="add_to_cart"),

    path("danh-muc/", dm.list_danh_muc, name="danh_muc_list"),
    path("danh-muc/create/", dm.create_danh_muc, name="danh_muc_create"),
    path("danh-muc/update/<str:id>/", dm.update_danh_muc, name="danh_muc_update"),
    path("danh-muc/delete/<str:id>/", dm.delete_danh_muc, name="danh_muc_delete"),
    
    path("checkout/", donhang.checkout_view, name="checkout"),
    path("orders/", donhang.orders_index, name="orders_index"),
    path("orders/<str:order_id>/", donhang.order_details, name="order_details"),
    path("orders/cancel/", donhang.cancel_order, name="cancel_order"),
    path("orders/place/", donhang.place_order, name="place_order"),  # 👈 thêm dòng này
    
    path("cart/", giohang.view_cart, name="view_cart"),

    # API cho sản phẩm
    path("api/products/", spv.products_list, name="api_products_list"),
    path("api/products/create/", spv.products_create, name="api_products_create"),
    # path("api/products/<str:id>/", spv.product_detail, name="api_product_detail"),
    
    # API
    path("api/orders/", dv.orders_list, name="api_orders_list"),
    path("api/orders/create/", dv.order_create, name="api_order_create"),
    path("api/orders/<str:id>/", dv.order_detail, name="api_order_detail"),
    path("api/cart/add/<str:sp_id>/", dv.api_add_to_cart, name="api_add_to_cart"),
    path("api/cart/badge/", dv.api_cart_badge, name="api_cart_badge"),
    
    # Admin (bị bảo vệ bởi decorator)
    path("admin-panel/", av.dashboard, name="admin_dashboard"),
    path("admin-panel/dashboard/", av.dashboard, name="admin_dashboard2"),
    # path("admin-panel/categories/", av.categories_list, name="admin_categories"),
    path("admin-panel/products/", spv.admin_products_list, name="admin_products"),
    
    #SanPhamThemXoaSua
    path("admin-panel/products/create/", spv.product_create, name="admin_product_create"),
    path("admin-panel/products/<str:id>/edit/", spv.product_edit, name="admin_product_edit"),
    path("admin-panel/products/<str:id>/delete/", spv.product_delete, name="admin_product_delete"),
    path("admin-panel/categories/", av.categories_list, name="admin_categories"),
    path("admin-panel/categories/create/", av.category_create, name="admin_category_create"),
    path("admin-panel/categories/<str:id>/edit/", av.category_edit, name="admin_category_edit"),
    path("admin-panel/categories/<str:id>/delete/", av.category_delete, name="admin_category_delete"),


    # Auth pages
    path("auth/login/",    ap.login_page,    name="auth_login_page"),
    path("auth/register/", ap.register_page, name="auth_register_page"),
    path("auth/logout/",   ap.logout_view,   name="auth_logout_page"),

    # Auth APIs
    path("api/auth/register", tv.auth_register),
    path("api/auth/login",    tv.auth_login),
    path("api/auth/logout",   tv.auth_logout),
    path("api/auth/me",       tv.auth_me),
]
