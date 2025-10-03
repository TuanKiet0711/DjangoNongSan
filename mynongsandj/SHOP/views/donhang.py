# shop/views/donhang.py
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from bson import ObjectId
from ..database import donhang, giohang, sanpham

# =============== DANH SÁCH ĐƠN CỦA TÔI =============== #
def orders_index(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("shop:auth_login_page")

    try:
        oid = ObjectId(user_id)
    except Exception:
        return redirect("shop:auth_login_page")

    cursor = donhang.find({"taiKhoanId": oid}).sort("ngayTao", -1)

    orders = []
    for d in cursor:
        sp = sanpham.find_one({"_id": d.get("sanPhamId")})
        orders.append({
            "id": str(d["_id"]),
            "ma_don_hang": str(d["_id"])[-6:].upper(),
            "tong_tien": int(d.get("tongTien", 0)),
            "trang_thai": d.get("trangThai", "cho_xu_ly"),
            "ngay_tao": d.get("ngayTao"),
            "so_luong": int(d.get("soLuong", 0)),
            "don_gia": int(d.get("donGia", 0)),
            "ten_san_pham": (sp or {}).get("tenSanPham") if sp else "Sản phẩm",
            "hinh_anh": ((sp or {}).get("hinhAnh") or [None])[0] if sp else None,
        })

    return render(request, "customer/indexdonhang.html", {"donhangs": orders})


# =============== CHI TIẾT ĐƠN =============== #
def order_details(request, order_id):
    try:
        oid = ObjectId(order_id)
    except Exception:
        return redirect("shop:orders_index")

    order = donhang.find_one({"_id": oid})
    if not order:
        return redirect("shop:orders_index")

    sp = sanpham.find_one({"_id": order.get("sanPhamId")})
    order_ctx = {
        "id": str(order["_id"]),
        "ma_don_hang": str(order["_id"])[-6:].upper(),
        "tong_tien": int(order.get("tongTien", 0)),
        "trang_thai": order.get("trangThai", "cho_xu_ly"),
        "ngay_tao": order.get("ngayTao"),
        "chi_tiet": [{
            "ten_san_pham": (sp or {}).get("tenSanPham") if sp else "Sản phẩm không tồn tại",
            "don_gia": int(order.get("donGia", 0)),
            "so_luong": int(order.get("soLuong", 0)),
            "thanh_tien": int(order.get("tongTien", 0)),
            "hinh_anh": ((sp or {}).get("hinhAnh") or [None])[0] if sp else None,
        }],
    }
    return render(request, "customer/details.html", {"donhang": order_ctx})


# =============== CHECKOUT =============== #
def checkout_view(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("shop:auth_login_page")

    try:
        oid = ObjectId(user_id)
    except Exception:
        return redirect("shop:auth_login_page")

    items, tong_tien = [], 0
    buy_now = (request.GET.get("buy_now") or "").strip()

    # Buy now: lưu vào session để place_order đọc được
    if buy_now:
        try:
            sp_oid = ObjectId(buy_now)
            sp = sanpham.find_one({"_id": sp_oid})
            if sp:
                dg = int(sp.get("gia", 0))
                item = {
                    "sanPhamId": sp["_id"],
                    "hinh_anh": (sp.get("hinhAnh") or [""])[0],
                    "tenSanPham": sp.get("tenSanPham"),
                    "don_gia": dg,
                    "so_luong": 1,
                    "thanh_tien": dg,
                }
                items.append(item)
                tong_tien = item["thanh_tien"]
                request.session["buy_now_id"] = str(sp_oid)
        except Exception:
            request.session.pop("buy_now_id", None)
    else:
        request.session.pop("buy_now_id", None)
        for gh in giohang.find({"taiKhoanId": oid}):
            sp = sanpham.find_one({"_id": gh["sanPhamId"]})
            if not sp:
                continue
            sl = int(gh.get("soLuong", 0))
            dg = int(gh.get("donGia", sp.get("gia", 0)))
            tt = int(gh.get("tongTien", sl * dg))
            items.append({
                "sanPhamId": sp["_id"],
                "hinh_anh": (sp.get("hinhAnh") or [""])[0],
                "tenSanPham": sp.get("tenSanPham"),
                "don_gia": dg,
                "so_luong": sl,
                "thanh_tien": tt,
            })
            tong_tien += tt

    ctx = {"items": items, "tong_tien": tong_tien, "today": timezone.now()}
    return render(request, "customer/checkout.html", ctx)


# =============== HỦY ĐƠN =============== #
def cancel_order(request):
    if request.method == "POST":
        order_id = request.POST.get("id")
        try:
            oid = ObjectId(order_id)
            donhang.update_one({"_id": oid}, {"$set": {"trangThai": "huy"}})
        except Exception:
            pass
    return redirect("shop:orders_index")


# =============== ĐẶT HÀNG =============== #
@require_POST
def place_order(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("shop:auth_login_page")

    try:
        uid = ObjectId(user_id)
    except Exception:
        return redirect("shop:auth_login_page")

    # Thông tin nhận hàng
    ho_ten = (request.POST.get("ho_ten") or "").strip()
    so_dien_thoai = (request.POST.get("so_dien_thoai") or "").strip()
    dia_chi = (request.POST.get("dia_chi") or "").strip()
    ngay_giao = (request.POST.get("ngay_giao") or "").strip()
    ghi_chu = (request.POST.get("ghi_chu") or "").strip()
    phuong_thuc = (request.POST.get("phuong_thuc_thanh_toan") or "COD").strip()

    docs = []
    now = timezone.now()

    # Ưu tiên BUY NOW nếu có trong session
    buy_now_id = request.session.pop("buy_now_id", None)
    if buy_now_id:
        try:
            sp = sanpham.find_one({"_id": ObjectId(buy_now_id)})
        except Exception:
            sp = None
        if sp:
            dg = int(sp.get("gia", 0))
            sl = 1
            docs.append({
                "taiKhoanId": uid,
                "sanPhamId": sp["_id"],
                "soLuong": sl,
                "donGia": dg,
                "tongTien": dg * sl,
                "ngayTao": now,
                "phuongThucThanhToan": phuong_thuc,
                "trangThai": "cho_xu_ly",
                # Info nhận hàng
                "hoTen": ho_ten, "soDienThoai": so_dien_thoai,
                "diaChi": dia_chi, "ngayGiao": ngay_giao, "ghiChu": ghi_chu,
            })
    else:
        # Lấy toàn bộ giỏ hàng
        cart = list(giohang.find({"taiKhoanId": uid}))
        if not cart:
            return redirect("shop:view_cart")
        for gh in cart:
            sp = sanpham.find_one({"_id": gh["sanPhamId"]})
            dg = int(gh.get("donGia", (sp or {}).get("gia", 0)))
            sl = int(gh.get("soLuong", 0))
            docs.append({
                "taiKhoanId": uid,
                "sanPhamId": gh["sanPhamId"],
                "soLuong": sl,
                "donGia": dg,
                "tongTien": dg * sl,
                "ngayTao": now,
                "phuongThucThanhToan": phuong_thuc,
                "trangThai": "cho_xu_ly",
                "hoTen": ho_ten, "soDienThoai": so_dien_thoai,
                "diaChi": dia_chi, "ngayGiao": ngay_giao, "ghiChu": ghi_chu,
            })

    if docs:
        donhang.insert_many(docs)
        # Xoá giỏ nếu đặt từ giỏ
        if not buy_now_id:
            giohang.delete_many({"taiKhoanId": uid})

    return redirect("shop:orders_index")
