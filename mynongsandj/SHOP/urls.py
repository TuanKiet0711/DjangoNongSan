from django.urls import path
from .views import danh_muc_view as dm
from .views import sanpham as sanpham
from .views import home, admin_view as av
from .views import taikhoan_view as tv
from .views import auth_pages as ap

app_name = "shop"

urlpatterns = [
    path("", home.home, name="home"),
    path("sanpham/", sanpham.sanpham_list, name="sanpham_list"),
    path("sanpham/category/<str:cat_id>/", sanpham.product_by_category, name="product_by_category"),
    path("sanpham/add/<str:sp_id>/", sanpham.add_to_cart, name="add_to_cart"),

    path("danh-muc/", dm.list_danh_muc, name="danh_muc_list"),
    path("danh-muc/create/", dm.create_danh_muc, name="danh_muc_create"),
    path("danh-muc/update/<str:id>/", dm.update_danh_muc, name="danh_muc_update"),
    path("danh-muc/delete/<str:id>/", dm.delete_danh_muc, name="danh_muc_delete"),

    # Admin (bị bảo vệ bởi decorator)
    path("admin-panel/", av.dashboard, name="admin_dashboard"),
    path("admin-panel/dashboard/", av.dashboard, name="admin_dashboard2"),
    # path("admin-panel/categories/", av.categories_list, name="admin_categories"),
    # path("admin-panel/products/", av.products_list, name="admin_products"),

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
