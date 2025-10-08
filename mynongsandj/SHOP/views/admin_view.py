# SHOP/views/admin_view.py
from django.shortcuts import render, redirect
from django.contrib import messages
from math import ceil
from datetime import timedelta
from django.utils import timezone
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
    # KPIs cơ bản
    total_products = san_pham.count_documents({})
    total_categories = danh_muc.count_documents({})
    total_orders = don_hang.count_documents({})
    total_accounts = tai_khoan.count_documents({})

    # Doanh thu
    now = timezone.localtime(timezone.now())
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = start_today.replace(day=1)
    tz_name = "Asia/Ho_Chi_Minh"
    ok_status = ["da_xac_nhan", "dang_giao", "hoan_thanh"]  # coi như đã bán

    def _sum(match):
        pipe = [
            {"$match": match},
            {"$group": {"_id": None, "revenue": {"$sum": "$tongTien"}, "orders": {"$sum": 1}}},
        ]
        data = list(don_hang.aggregate(pipe))
        if data:
            return int(data[0]["revenue"]), int(data[0]["orders"])
        return 0, 0

    revenue_today, orders_today = _sum({"trangThai": {"$in": ok_status}, "ngayTao": {"$gte": start_today}})
    revenue_month, orders_month = _sum({"trangThai": {"$in": ok_status}, "ngayTao": {"$gte": start_month}})

    # ---- Revenue by DAY (14 d) ----
    day_from = start_today - timedelta(days=13)
    day_pipe = [
        {"$match": {"trangThai": {"$in": ok_status}, "ngayTao": {"$gte": day_from}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ngayTao", "timezone": tz_name}},
            "revenue": {"$sum": "$tongTien"}
        }},
        {"$sort": {"_id": 1}},
    ]
    day_map = {d["_id"]: int(d["revenue"]) for d in don_hang.aggregate(day_pipe)}
    daily_labels, daily_values = [], []
    for i in range(14):
        d = (day_from + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_labels.append(d)
        daily_values.append(day_map.get(d, 0))

    # ---- Revenue by MONTH (12 m) ----
    def month_add(dt, k):
        m = dt.month - 1 + k
        y = dt.year + m // 12
        m = m % 12 + 1
        return dt.replace(year=y, month=m, day=1)

    first_this_month = start_month
    month_start = month_add(first_this_month, -11)

    mon_pipe = [
        {"$match": {"trangThai": {"$in": ok_status}, "ngayTao": {"$gte": month_start}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$ngayTao", "timezone": tz_name}},
            "revenue": {"$sum": "$tongTien"}
        }},
        {"$sort": {"_id": 1}},
    ]
    mon_map = {d["_id"]: int(d["revenue"]) for d in don_hang.aggregate(mon_pipe)}
    monthly_labels, monthly_values = [], []
    cur_m = month_start
    for _ in range(12):
        label = cur_m.strftime("%Y-%m")
        monthly_labels.append(label)
        monthly_values.append(mon_map.get(label, 0))
        cur_m = month_add(cur_m, 1)

    ctx = {
        "total_products": total_products,
        "total_categories": total_categories,
        "total_orders": total_orders,
        "total_accounts": total_accounts,

        "revenue_today": revenue_today,
        "revenue_month": revenue_month,
        "orders_today": orders_today,
        "orders_month": orders_month,

        "daily_labels": daily_labels,
        "daily_values": daily_values,
        "monthly_labels": monthly_labels,
        "monthly_values": monthly_values,
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
    return render(request, "shop/admin/categories/list.html", ctx)

@admin_required
def category_create(request):
    col, storage_field = _col_danhmuc()

    if request.method == "GET":
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

PAGE_SIZE = 6

@admin_required
def accounts_list(request):
    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("vaiTro") or "").strip()
    page = max(int(request.GET.get("page", 1)), 1)

    page_size = PAGE_SIZE

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
        return render(request, "shop/admin/accounts/edit.html", {"account": {
            "id": str(acc["_id"]),
            "hoTen": acc.get("hoTen", ""),
            "email": acc.get("email", ""),
            "sdt": acc.get("sdt", ""),
            "vaiTro": acc.get("vaiTro", "customer"),
        }})

    hoTen = (request.POST.get("hoTen") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    sdt = (request.POST.get("sdt") or "").strip()
    matKhau = (request.POST.get("matKhau") or "").strip()
    vaiTro = (request.POST.get("vaiTro") or "").strip()

    update = {"hoTen": hoTen, "email": email, "sdt": sdt, "vaiTro": vaiTro}
    if matKhau:
        update["matKhau"] = matKhau

    if tai_khoan.find_one({"email": email, "_id": {"$ne": oid}}):
        messages.error(request, "Email đã tồn tại.")
        return redirect("shop:admin_account_edit", id=id)

    tai_khoan.update_one({"_id": oid}, {"$set": update})
    messages.success(request, "Cập nhật tài khoản thành công.")
    return redirect("shop:admin_accounts")


@admin_required
def account_delete(request, id):
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
        return render(request, "shop/admin/accounts/delete.html", {"account": {
            "id": str(acc["_id"]),
            "hoTen": acc.get("hoTen", ""),
            "email": acc.get("email", ""),
            "sdt": acc.get("sdt", ""),
            "vaiTro": acc.get("vaiTro", "customer"),
        }})

    tai_khoan.delete_one({"_id": oid})
    messages.success(request, "Đã xoá tài khoản.")
    return redirect("shop:admin_accounts")
# =================== ORDERS (ADMIN) =================== #

ORDER_STATUSES = ["cho_xu_ly", "da_xac_nhan", "dang_giao", "hoan_thanh", "da_huy"]
PM_LABELS = {"cod": "COD", "chuyen_khoan": "Chuyển khoản"}

def _fmt_money(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)

def _badge_status(st):
    return {
        "cho_xu_ly": "secondary",
        "da_xac_nhan": "info",
        "dang_giao": "warning",
        "hoan_thanh": "success",
        "da_huy": "danger",
    }.get(st, "secondary")

@admin_required
def orders_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    page = max(int(request.GET.get("page", 1)), 1)
    page_size = PAGE_SIZE

    # ---- BUILD FILTER ----
    flt = {}
    if status:
        flt["trangThai"] = status

    ors = []
    if q:
        # Khớp theo mã đơn (_id)
        oid = _safe_oid(q)
        if oid:
            ors.append({"_id": oid})

        # Khớp theo thông tin giao hàng (tên/SĐT/địa chỉ)
        ors += [
            {"shipping.hoTen": {"$regex": q, "$options": "i"}},
            {"shipping.soDienThoai": {"$regex": q, "$options": "i"}},
            {"shipping.diaChi": {"$regex": q, "$options": "i"}},
        ]

        # 🎯 Khớp theo TÀI KHOẢN: tìm _id các account có tên/email/SĐT khớp
        acc_ids = [
            a["_id"] for a in tai_khoan.find(
                {
                    "$or": [
                        {"hoTen": {"$regex": q, "$options": "i"}},
                        {"email": {"$regex": q, "$options": "i"}},
                        {"sdt":   {"$regex": q, "$options": "i"}},
                    ]
                },
                {"_id": 1}
            )
        ]
        if acc_ids:
            ors.append({"taiKhoanId": {"$in": acc_ids}})

    if ors:
        flt["$or"] = ors

    # ---- PAGINATION ----
    total = don_hang.count_documents(flt)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    skip = (page - 1) * page_size

    cursor = don_hang.find(flt).sort("ngayTao", -1).skip(skip).limit(page_size)
    docs = list(cursor)

    # ---- MAP TRẠNG THÁI + TÊN TÀI KHOẢN ----
    status_labels = {
        "cho_xu_ly": "Chờ xử lý",
        "da_xac_nhan": "Đã xác nhận",
        "dang_giao": "Đang giao",
        "hoan_thanh": "Hoàn thành",
        "da_huy": "Đã hủy",
    }

    # Lấy danh sách user id để map tên
    user_ids = {d["taiKhoanId"] for d in docs if d.get("taiKhoanId")}
    user_map = {}
    if user_ids:
        for acc in tai_khoan.find({"_id": {"$in": list(user_ids)}}, {"hoTen": 1}):
            user_map[str(acc["_id"])] = acc.get("hoTen", "(Không tên)")

    items = []
    for d in docs:
        trang_thai = d.get("trangThai", "")
        uid_str = str(d.get("taiKhoanId", ""))

        items.append({
            "id": str(d["_id"]),
            "maNgan": str(d["_id"])[-6:],
            "taiKhoanTen": user_map.get(uid_str, uid_str[:8] if uid_str else "—"),
            "tongTienFmt": _fmt_money(d.get("tongTien", 0)),
            "pttt": PM_LABELS.get(d.get("phuongThucThanhToan", ""), d.get("phuongThucThanhToan", "")),
            "trangThai": trang_thai,
            "badge": _badge_status(trang_thai),
            "trangThaiLabel": status_labels.get(trang_thai, trang_thai),
            "ngayTao": d.get("ngayTao"),
        })

    ctx = {
        "items": items,
        "q": q,
        "status": status,
        "statuses": ORDER_STATUSES,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "page_numbers": list(range(1, total_pages + 1)),
    }
    return render(request, "shop/admin/orders/list.html", ctx)




@admin_required
def order_details(request, id):
    oid = _safe_oid(id)
    if not oid:
        messages.error(request, "ID không hợp lệ.")
        return redirect("shop:admin_orders")

    d = don_hang.find_one({"_id": oid})
    if not d:
        messages.error(request, "Không tìm thấy đơn hàng.")
        return redirect("shop:admin_orders")

    ship = d.get("shipping", {}) or {}
    items = []
    for it in (d.get("items") or []):
        items.append({
            "ten": it.get("tenSanPham", ""),
            "soLuong": int(it.get("soLuong", 0)),
            "donGiaFmt": _fmt_money(it.get("donGia", 0)),
            "thanhTienFmt": _fmt_money(it.get("thanhTien", 0)),
        })

    ctx = {
        "id": str(d["_id"]),
        "pttt": PM_LABELS.get(d.get("phuongThucThanhToan", ""), d.get("phuongThucThanhToan", "")),
        "trangThai": d.get("trangThai", ""),
        "badge": _badge_status(d.get("trangThai", "")),
        "tongTienFmt": _fmt_money(d.get("tongTien", 0)),
        "ngayTao": d.get("ngayTao"),
        "ngayCapNhat": d.get("ngayCapNhat"),
        "ship": {
            "hoTen": ship.get("hoTen", ""),
            "sdt": ship.get("soDienThoai", ""),
            "diaChi": ship.get("diaChi", ""),
            "ngayGiao": ship.get("ngayGiao", ""),
            "ghiChu": ship.get("ghiChu", ""),
        },
        "items": items,
    }
    return render(request, "shop/admin/orders/details.html", ctx)

def _img_url_from_product(sp):
    """Trả về URL ảnh hiển thị từ document sản phẩm."""
    if not sp:
        return "/static/img/placeholder.png"

    # các key đơn
    candidates = [sp.get("anh"), sp.get("hinhAnh"), sp.get("image")]
    # các key list
    for list_key in ("images", "hinhAnhs", "hinh_anh"):
        lst = sp.get(list_key)
        if isinstance(lst, list) and lst:
            candidates.append(lst[0])

    for path in candidates:
        if isinstance(path, str) and path.strip():
            p = path.strip()
            if p.startswith("http://") or p.startswith("https://") or p.startswith("/media/"):
                return p
            # coi như path tương đối trong MEDIA_ROOT
            return f"/media/{p.lstrip('/')}"
    return "/static/img/placeholder.png"


@admin_required
def order_edit(request, id):
    oid = _safe_oid(id)
    if not oid:
        messages.error(request, "ID không hợp lệ.")
        return redirect("shop:admin_orders")

    d = don_hang.find_one({"_id": oid})
    if not d:
        messages.error(request, "Không tìm thấy đơn hàng.")
        return redirect("shop:admin_orders")

    # Map trạng thái -> label tiếng Việt
    status_labels = {
        "cho_xu_ly": "Chờ xử lý",
        "da_xac_nhan": "Đã xác nhận",
        "dang_giao": "Đang giao",
        "hoan_thanh": "Hoàn thành",
        "da_huy": "Đã hủy",
    }
    status_choices = [(k, v) for k, v in status_labels.items()]

    if request.method == "GET":
        ship = d.get("shipping", {}) or {}

        # ---- Chỉ hiển thị TÊN SP lấy từ snapshot trong đơn (không join DB) ----
        items_vm = []
        tong = int(d.get("tongTien", 0))

        for it in (d.get("items") or []):
            ten_sp = (it.get("tenSanPham") or "").strip() or "(Chưa có tên)"
            don_gia = int(it.get("donGia", 0))
            so_luong = int(it.get("soLuong", 0))
            thanh_tien = int(it.get("thanhTien", don_gia * so_luong))

            items_vm.append({
                "ten": ten_sp,
                "donGiaFmt": _fmt_money(don_gia),
                "soLuong": so_luong,
                "thanhTienFmt": _fmt_money(thanh_tien),
            })

        ctx = {
            "id": str(d["_id"]),
            "cur_status": d.get("trangThai", ""),
            "statuses": [k for k, _ in status_choices],
            "status_choices": status_choices,
            "cur_status_label": status_labels.get(d.get("trangThai", ""), d.get("trangThai", "")),

            "pttt_label": PM_LABELS.get(d.get("phuongThucThanhToan", ""), d.get("phuongThucThanhToan", "")),
            "tongTienFmt": _fmt_money(tong),

            "ship": {
                "hoTen": ship.get("hoTen", ""),
                "soDienThoai": ship.get("soDienThoai", ""),
                "diaChi": ship.get("diaChi", ""),
                "ngayGiao": ship.get("ngayGiao", ""),
                "ghiChu": ship.get("ghiChu", ""),
            },
            "items": items_vm,
            "ngayTao": d.get("ngayTao"),
            "ngayCapNhat": d.get("ngayCapNhat"),
        }
        return render(request, "shop/admin/orders/edit.html", ctx)

    # POST: chỉ cho phép đổi TRẠNG THÁI
    st = (request.POST.get("trangThai") or "").strip()
    ORDER_STATUSES = ["cho_xu_ly", "da_xac_nhan", "dang_giao", "hoan_thanh", "da_huy"]
    if st not in ORDER_STATUSES:
        messages.error(request, "Trạng thái không hợp lệ.")
        return redirect("shop:admin_order_edit", id=id)

    don_hang.update_one({"_id": oid}, {"$set": {
        "trangThai": st,
        "ngayCapNhat": timezone.now(),
    }})
    messages.success(request, "Cập nhật trạng thái đơn hàng thành công.")
    return redirect("shop:admin_orders")


@admin_required
def order_delete(request, id):
    oid = _safe_oid(id)
    if not oid:
        messages.error(request, "ID không hợp lệ.")
        return redirect("shop:admin_orders")

    d = don_hang.find_one({"_id": oid})
    if not d:
        messages.error(request, "Không tìm thấy đơn hàng.")
        return redirect("shop:admin_orders")

    # chỉ cho phép xóa các trạng thái sau
    allowed_status = ["cho_xu_ly", "da_xac_nhan", "da_huy"]
    cur_status = d.get("trangThai", "")

    if cur_status not in allowed_status:
        messages.error(
            request,
            "Chỉ có thể xóa đơn ở trạng thái: Chờ xử lý, Đã xác nhận hoặc Đã hủy."
        )
        return redirect("shop:admin_orders")

    status_labels = {
        "cho_xu_ly": "Chờ xử lý",
        "da_xac_nhan": "Đã xác nhận",
        "dang_giao": "Đang giao",
        "hoan_thanh": "Hoàn thành",
        "da_huy": "Đã hủy",
    }

    if request.method == "GET":
        ship = d.get("shipping", {}) or {}
        items_vm = []
        tong = int(d.get("tongTien", 0))

        for it in (d.get("items") or []):
            ten_sp = (it.get("tenSanPham") or "").strip() or "(Chưa có tên)"
            don_gia = int(it.get("donGia", 0))
            so_luong = int(it.get("soLuong", 0))
            thanh_tien = int(it.get("thanhTien", don_gia * so_luong))

            items_vm.append({
                "ten": ten_sp,
                "donGiaFmt": _fmt_money(don_gia),
                "soLuong": so_luong,
                "thanhTienFmt": _fmt_money(thanh_tien),
            })

        ctx = {
            "id": str(d["_id"]),
            "trangThai": cur_status,
            "trangThaiLabel": status_labels.get(cur_status, cur_status),
            "badge": _badge_status(cur_status),
            "pttt_label": PM_LABELS.get(d.get("phuongThucThanhToan", ""), d.get("phuongThucThanhToan", "")),
            "tongTienFmt": _fmt_money(tong),
            "ship": {
                "hoTen": ship.get("hoTen", ""),
                "soDienThoai": ship.get("soDienThoai", ""),
                "diaChi": ship.get("diaChi", ""),
                "ngayGiao": ship.get("ngayGiao", ""),
                "ghiChu": ship.get("ghiChu", ""),
            },
            "items": items_vm,
            "ngayTao": d.get("ngayTao"),
        }
        return render(request, "shop/admin/orders/delete.html", ctx)

    # POST: thực hiện xóa
    don_hang.delete_one({"_id": oid})
    messages.success(request, "Đã xoá đơn hàng thành công.")
    return redirect("shop:admin_orders")
