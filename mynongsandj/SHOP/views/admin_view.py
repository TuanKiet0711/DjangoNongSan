# SHOP/views/admin_view.py
from django.shortcuts import render, redirect
from django.contrib import messages
from math import ceil
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from .admin_required import admin_required
from ..database import (
    sanpham as san_pham,
    danhmuc as danh_muc,
    donhang as don_hang,
    taikhoan as tai_khoan
)
# dùng lại helper của API để thống nhất collection/field
from .danh_muc_view import _col_danhmuc

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

# =================== CATEGORIES (ADMIN) =================== #
def _safe_oid(s):
    try:
        return ObjectId(s)
    except (InvalidId, TypeError):
        return None
@admin_required
def categories_list(request):
    q = (request.GET.get("q") or "").strip()
    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except ValueError:
        page = 1

    col, storage_field = _col_danhmuc()
    query = {storage_field: {"$regex": q, "$options": "i"}} if q else {}
    total = col.count_documents(query)

    total_pages = max(1, ceil(total / PAGE_SIZE))
    page = min(page, total_pages)
    skip = (page - 1) * PAGE_SIZE

    cursor = (col.find(query).sort(storage_field, 1).skip(skip).limit(PAGE_SIZE))
    items = [{"id": str(dm["_id"]), "tenDanhMuc": dm.get(storage_field, "")} for dm in cursor]

    ctx = {
        "items": items,
        "q": q,
        "page": page,
        "page_size": PAGE_SIZE,
        "total_pages": total_pages,
        "total": total,
        "page_numbers": list(range(1, total_pages + 1)),
        "start_index": skip + 1,
    }
    # 👇 ĐÚNG THƯ MỤC: admin/categories/list.html
    return render(request, "shop/admin/categories/list.html", ctx)

@admin_required
def category_create(request):
    col, storage_field = _col_danhmuc()

    if request.method == "GET":
        # 👇 admin/categories/create.html
        return render(request, "shop/admin/categories/create.html")

    name = (request.POST.get("tenDanhMuc") or "").strip()
    if not name:
        messages.error(request, "Vui lòng nhập tên danh mục.")
        return redirect("shop:admin_category_create")

    try:
        col.insert_one({storage_field: name})
        messages.success(request, f"Đã thêm danh mục: {name}")
        return redirect("shop:admin_categories")
    except DuplicateKeyError:
        messages.error(request, "Danh mục đã tồn tại.")
        return redirect("shop:admin_category_create")

@admin_required
def category_edit(request, id):
    col, storage_field = _col_danhmuc()
    oid = _safe_oid(id)
    if not oid:
        messages.error(request, "ID không hợp lệ.")
        return redirect("shop:admin_categories")

    dm = col.find_one({"_id": oid})
    if not dm:
        messages.error(request, "Không tìm thấy danh mục.")
        return redirect("shop:admin_categories")

    if request.method == "GET":
        # 👇 admin/categories/edit.html
        return render(request, "shop/admin/categories/edit.html",
                      {"id": id, "tenDanhMuc": dm.get(storage_field, "")})

    name = (request.POST.get("tenDanhMuc") or "").strip()
    if not name:
        messages.error(request, "Vui lòng nhập tên danh mục.")
        return redirect("shop:admin_category_edit", id=id)

    try:
        res = col.update_one({"_id": oid}, {"$set": {storage_field: name}})
        if res.matched_count == 0:
            messages.error(request, "Không tìm thấy danh mục cần sửa.")
        else:
            messages.success(request, "Cập nhật danh mục thành công.")
    except DuplicateKeyError:
        messages.error(request, "Tên danh mục bị trùng.")
    return redirect("shop:admin_categories")

@admin_required
def category_delete(request, id):
    col, _ = _col_danhmuc()
    oid = _safe_oid(id)
    if not oid:
        messages.error(request, "ID không hợp lệ.")
        return redirect("shop:admin_categories")

    if request.method == "GET":
        dm = col.find_one({"_id": oid}) or {}
        name = dm.get("tenDanhMuc") or dm.get("ten_danh_muc") or ""
        # 👇 admin/categories/delete.html
        return render(request, "shop/admin/categories/delete.html",
                      {"id": id, "tenDanhMuc": name})

    res = col.delete_one({"_id": oid})
    if res.deleted_count == 0:
        messages.error(request, "Không tìm thấy danh mục để xoá.")
    else:
        messages.success(request, "Đã xoá danh mục.")
    return redirect("shop:admin_categories")
# =================== ACCOUNTS (ADMIN) =================== #
from .taikhoan_view import _safe_user
from ..database import taikhoan as tai_khoan

# SHOP/views/admin_view.py

PAGE_SIZE = 6  # bạn đã có ở trên, tận dụng luôn

@admin_required
def accounts_list(request):
    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("vaiTro") or "").strip()
    page = max(int(request.GET.get("page", 1)), 1)

    page_size = PAGE_SIZE  # 👈 đổi từ 10 thành 6 (dùng hằng có sẵn)

    filter_ = {}
    if q:
        filter_["$or"] = [
            {"hoTen": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"sdt": {"$regex": q, "$options": "i"}},
        ]
    if role:
        filter_["vaiTro"] = role

    total = tai_khoan.count_documents(filter_)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    skip = (page - 1) * page_size

    cursor = tai_khoan.find(filter_).sort("hoTen", 1).skip(skip).limit(page_size)
    items = [_safe_user(acc) for acc in cursor]

    ctx = {
        "items": items,
        "q": q,
        "role": role,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "page_numbers": list(range(1, total_pages + 1)),
    }
    return render(request, "shop/admin/accounts/list.html", ctx)


@admin_required
def account_create(request):
    if request.method == "GET":
        return render(request, "shop/admin/accounts/create.html")

    hoTen = (request.POST.get("hoTen") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    sdt = (request.POST.get("sdt") or "").strip()
    matKhau = (request.POST.get("matKhau") or "").strip()
    vaiTro = (request.POST.get("vaiTro") or "customer").strip() or "customer"

    if not hoTen or not email or not matKhau:
        messages.error(request, "Vui lòng nhập đủ Họ tên, Email, Mật khẩu.")
        return redirect("shop:admin_account_create")

    if tai_khoan.find_one({"email": email}):
        messages.error(request, "Email đã tồn tại.")
        return redirect("shop:admin_account_create")

    tai_khoan.insert_one({
        "hoTen": hoTen, "email": email, "sdt": sdt,
        "matKhau": matKhau, "vaiTro": vaiTro
    })
    messages.success(request, f"Đã thêm tài khoản: {hoTen}")
    return redirect("shop:admin_accounts")


@admin_required
def account_edit(request, id):
    from bson import ObjectId
    try:
        oid = ObjectId(id)
    except Exception:
        messages.error(request, "ID không hợp lệ.")
        return redirect("shop:admin_accounts")

    acc = tai_khoan.find_one({"_id": oid})
    if not acc:
        messages.error(request, "Không tìm thấy tài khoản.")
        return redirect("shop:admin_accounts")

    if request.method == "GET":
        return render(request, "shop/admin/accounts/edit.html", {"account": _safe_user(acc)})

    hoTen = (request.POST.get("hoTen") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    sdt = (request.POST.get("sdt") or "").strip()
    matKhau = (request.POST.get("matKhau") or "").strip()
    vaiTro = (request.POST.get("vaiTro") or "").strip()

    update = {"hoTen": hoTen, "email": email, "sdt": sdt, "vaiTro": vaiTro}
    if matKhau:
        update["matKhau"] = matKhau

    # check email trùng
    if tai_khoan.find_one({"email": email, "_id": {"$ne": oid}}):
        messages.error(request, "Email đã tồn tại.")
        return redirect("shop:admin_account_edit", id=id)

    tai_khoan.update_one({"_id": oid}, {"$set": update})
    messages.success(request, "Cập nhật tài khoản thành công.")
    return redirect("shop:admin_accounts")


@admin_required
def account_delete(request, id):
    from bson import ObjectId
    try:
        oid = ObjectId(id)
    except Exception:
        messages.error(request, "ID không hợp lệ.")
        return redirect("shop:admin_accounts")

    acc = tai_khoan.find_one({"_id": oid})
    if not acc:
        messages.error(request, "Không tìm thấy tài khoản.")
        return redirect("shop:admin_accounts")

    if request.method == "GET":
        return render(request, "shop/admin/accounts/delete.html", {"account": _safe_user(acc)})

    tai_khoan.delete_one({"_id": oid})
    messages.success(request, "Đã xoá tài khoản.")
    return redirect("shop:admin_accounts")
