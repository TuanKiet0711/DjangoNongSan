# SHOP/urls.py
from django.urls import path
from .views import danh_muc_view as dm
from .views import taikhoan_view as v
from .views import home
from .views import sanpham as sanpham
from .views import home, sanpham, admin_view as av   # file shop/views/admin_views.py
app_name = "shop"  # optional, để namespace

urlpatterns = [
    path("createsuperadmin/", v.createsuperadmin, name="createsuperadmin"),
    path("", home.home, name="home"),
    path("sanpham/", sanpham.sanpham_list, name="sanpham_list"),
    path("sanpham/category/<str:cat_id>/", sanpham.product_by_category, name="product_by_category"),
    path("sanpham/add/<str:sp_id>/", sanpham.add_to_cart, name="add_to_cart"),
    # Danh mục (có dấu / ở cuối như bạn yêu cầu)
    path("danh-muc/", dm.list_danh_muc, name="danh_muc_list"),
    path("danh-muc/create/", dm.create_danh_muc, name="danh_muc_create"),
    path("danh-muc/update/<str:id>/", dm.update_danh_muc, name="danh_muc_update"),
    path("danh-muc/delete/<str:id>/", dm.delete_danh_muc, name="danh_muc_delete"),
    # path("api/accounts/", v.accounts_list),  # list
    # path("api/accounts/create", v.accounts_create),  # create
    # path("api/accounts/<str:id>/edit", v.accounts_edit),  # edit
    # path("api/accounts/<str:id>/delete", v.accounts_delete),  # delete

    # # auth
    # path("api/auth/register", v.auth_register),
    # path("api/auth/login",    v.auth_login),
    # path("api/auth/logout",   v.auth_logout),
    # path("api/auth/me",       v.auth_me),
    
     # ====== Admin Panel (HTML) ======
    path("admin-panel/", av.dashboard, name="admin_dashboard"),
    # path("admin-panel/categories/", av.categories_list, name="admin_categories"),
    # path("admin-panel/products/", av.products_list, name="admin_products"),
]
