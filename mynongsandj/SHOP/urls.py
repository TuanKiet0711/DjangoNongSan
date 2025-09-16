# SHOP/urls.py
from django.urls import path
from .views import danh_muc_view as dm

app_name = "shop"  # optional, để namespace

urlpatterns = [
    # Danh mục (có dấu / ở cuối như bạn yêu cầu)
    path("danh-muc/", dm.list_danh_muc, name="danh_muc_list"),
    path("danh-muc/create/", dm.create_danh_muc, name="danh_muc_create"),
    path("danh-muc/update/<str:id>/", dm.update_danh_muc, name="danh_muc_update"),
    path("danh-muc/delete/<str:id>/", dm.delete_danh_muc, name="danh_muc_delete"),
]
