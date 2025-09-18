# SHOP/urls.py
from django.urls import path
from .views import danh_muc_view as dm
from .views import taikhoan_view as v
app_name = "shop"  # optional, để namespace

urlpatterns = [
    # Danh mục (có dấu / ở cuối như bạn yêu cầu)
    path("danh-muc/", dm.list_danh_muc, name="danh_muc_list"),
    path("danh-muc/create/", dm.create_danh_muc, name="danh_muc_create"),
    path("danh-muc/update/<str:id>/", dm.update_danh_muc, name="danh_muc_update"),
    path("danh-muc/delete/<str:id>/", dm.delete_danh_muc, name="danh_muc_delete"),
    path("api/accounts/", v.accounts_list),  # list
    path("api/accounts/create", v.accounts_create),  # create
    path("api/accounts/<str:id>/edit", v.accounts_edit),  # edit
    path("api/accounts/<str:id>/delete", v.accounts_delete),  # delete

    # auth
    path("api/auth/register", v.auth_register),
    path("api/auth/login",    v.auth_login),
    path("api/auth/logout",   v.auth_logout),
    path("api/auth/me",       v.auth_me),
]
