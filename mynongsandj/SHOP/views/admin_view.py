# SHOP/views/admin_view.py
from django.shortcuts import render
from math import ceil
from bson import ObjectId
from .admin_required import admin_required
from ..database import (
    sanpham as san_pham,
    danhmuc as danh_muc,
    donhang as don_hang,
    taikhoan as tai_khoan
)

PAGE_SIZE = 6

# =================== DASHBOARD =================== #
@admin_required
def dashboard(request):
    ctx = {
        "total_products": san_pham.count_documents({}),
        "total_categories": danh_muc.count_documents({}),
        "total_orders": don_hang.count_documents({}),
        "total_accounts": tai_khoan.count_documents({}),
    }
    return render(request, "shop/admin/dashboard.html", ctx)
# # =================== CATEGORIES =================== #

# def categories_list(request):
#     q = (request.GET.get("q") or "").strip()
#     try:
#         page = max(int(request.GET.get("page", 1)), 1)
#     except ValueError:
#         page = 1

#     filter_ = {}
#     if q:
#         filter_["ten_danh_muc"] = {"$regex": q, "$options": "i"}

#     total = danh_muc.count_documents(filter_)
#     total_pages = max(1, ceil(total / PAGE_SIZE))
#     page = min(page, total_pages)
#     skip = (page - 1) * PAGE_SIZE

#     cursor = (
#         danh_muc.find(filter_, {"ten_danh_muc": 1})
#         .sort("ten_danh_muc", 1)
#         .skip(skip)
#         .limit(PAGE_SIZE)
#     )
#     items = [
#         {"id": str(dm["_id"]), "ten": dm.get("ten_danh_muc") or "Danh mục"}
#         for dm in cursor
#     ]

#     ctx = {
#         "items": items,
#         "q": q,
#         "page": page,
#         "total_pages": total_pages,
#         "total": total,
#         "has_prev": page > 1,
#         "has_next": page < total_pages,
#         "page_numbers": list(range(1, total_pages + 1)),
#     }
#     return render(request, "shop/admin/categories_list.html", ctx)

# # =================== PRODUCTS =================== #

# def products_list(request):
#     q = (request.GET.get("q") or "").strip()
#     try:
#         page = max(int(request.GET.get("page", 1)), 1)
#     except ValueError:
#         page = 1

#     filter_ = {}
#     if q:
#         filter_["ten_san_pham"] = {"$regex": q, "$options": "i"}

#     total = san_pham.count_documents(filter_)
#     total_pages = max(1, ceil(total / PAGE_SIZE))
#     page = min(page, total_pages)
#     skip = (page - 1) * PAGE_SIZE

#     cursor = (
#         san_pham.find(filter_, {"ten_san_pham": 1, "gia": 1, "danh_muc_id": 1, "hinh_anh": 1})
#         .sort("ten_san_pham", 1)
#         .skip(skip)
#         .limit(PAGE_SIZE)
#     )

#     items = []
#     for sp in cursor:
#         cat_name = "—"
#         if sp.get("danh_muc_id"):
#             try:
#                 cat = danh_muc.find_one({"_id": ObjectId(sp["danh_muc_id"])}, {"ten_danh_muc": 1})
#                 if cat:
#                     cat_name = cat.get("ten_danh_muc", "—")
#             except Exception:
#                 pass

#         items.append({
#             "id": str(sp["_id"]),
#             "ten": sp.get("ten_san_pham") or "Sản phẩm",
#             "gia": sp.get("gia", 0),
#             "hinh_anh": sp["hinh_anh"][0] if sp.get("hinh_anh") else None,
#             "danh_muc": cat_name,
#         })

#     ctx = {
#         "items": items,
#         "q": q,
#         "page": page,
#         "total_pages": total_pages,
#         "total": total,
#         "has_prev": page > 1,
#         "has_next": page < total_pages,
#         "page_numbers": list(range(1, total_pages + 1)),
#     }
#     return render(request, "shop/admin/products_list.html", ctx)
