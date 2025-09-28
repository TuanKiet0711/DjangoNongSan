# shop/views/donhang.py
from django.shortcuts import render, redirect
from django.utils import timezone
from bson import ObjectId
from ..database import donhang, giohang, sanpham
from django.views.decorators.http import require_POST

# Danh sách đơn hàng của user
def orders_index(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("shop:auth_login_page")

    oid = ObjectId(user_id)
    orders = list(donhang.find({"taiKhoanId": oid}).sort("ngayTao", -1))

    for d in orders:
        d["id"] = str(d["_id"])
        d["ma_don_hang"] = str(d["_id"])[-6:].upper()
        d["tong_tien"] = d.get("tongTien", 0)
        d["trang_thai"] = d.get("trangThai", "cho_xu_ly")

    return render(request, "customer/indexdonhang.html", {"donhangs": orders})


# Chi tiết đơn hàng
def order_details(request, order_id):
    try:
        oid = ObjectId(order_id)
    except Exception:
        return redirect("shop:orders_index")

    order = donhang.find_one({"_id": oid})
    if not order:
        return redirect("shop:orders_index")

    order["id"] = str(order["_id"])
    order["ma_don_hang"] = str(order["_id"])[-6:].upper()
    order["tong_tien"] = order.get("tongTien", 0)
    order["trang_thai"] = order.get("trangThai", "cho_xu_ly")

    # chỉ demo đơn giản: mỗi đơn có 1 sản phẩm
    sp = sanpham.find_one({"_id": order["sanPhamId"]})
    chi_tiet = [{
        "ten_san_pham": sp.get("tenSanPham") if sp else "Sản phẩm không tồn tại",
        "don_gia": order.get("donGia", 0),
        "so_luong": order.get("soLuong", 0),
        "thanh_tien": order.get("tongTien", 0),
    }]
    order["chi_tiet"] = chi_tiet

    return render(request, "customer/details.html", {"donhang": order})


# Trang checkout: lấy từ giỏ hàng
def checkout_view(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("shop:auth_login_page")

    oid = ObjectId(user_id)
    items = []
    tong_tien = 0

    buy_now = request.GET.get("buy_now")
    if buy_now:
        try:
            sp_oid = ObjectId(buy_now)
            sp = sanpham.find_one({"_id": sp_oid})
            if sp:
                item = {
                    "hinh_anh": (sp.get("hinhAnh") or [""])[0],
                    "tenSanPham": sp.get("tenSanPham"),
                    "don_gia": sp.get("gia", 0),
                    "so_luong": 1,
                    "thanh_tien": sp.get("gia", 0),
                }
                items.append(item)
                tong_tien = item["thanh_tien"]
        except Exception:
            pass
    else:
        # checkout từ giỏ hàng
        for gh in giohang.find({"taiKhoanId": oid}):
            sp = sanpham.find_one({"_id": gh["sanPhamId"]})
            if not sp: continue
            item = {
                "hinh_anh": (sp.get("hinhAnh") or [""])[0],
                "tenSanPham": sp.get("tenSanPham"),
                "don_gia": gh.get("donGia", 0),
                "so_luong": gh.get("soLuong", 0),
                "thanh_tien": gh.get("tongTien", 0),
            }
            items.append(item)
            tong_tien += item["thanh_tien"]

    ctx = {
        "items": items,
        "tong_tien": tong_tien,
        "today": timezone.now(),
    }
    return render(request, "customer/checkout.html", ctx)



# Hủy đơn hàng
def cancel_order(request):
    if request.method == "POST":
        order_id = request.POST.get("id")
        try:
            oid = ObjectId(order_id)
            donhang.update_one({"_id": oid}, {"$set": {"trangThai": "huy"}})
        except Exception:
            pass
    return redirect("shop:orders_index")

@require_POST
def place_order(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("shop:auth_login_page")

    oid = ObjectId(user_id)

    ho_ten = request.POST.get("ho_ten")
    so_dien_thoai = request.POST.get("so_dien_thoai")
    dia_chi = request.POST.get("dia_chi")
    ngay_giao = request.POST.get("ngay_giao")
    ghi_chu = request.POST.get("ghi_chu")
    phuong_thuc = request.POST.get("phuong_thuc_thanh_toan", "COD")

    # TODO: lấy items từ giỏ hàng hoặc buy_now (tuỳ bạn đã set)
    # demo đơn giản: lưu 1 đơn fake
    order_doc = {
        "taiKhoanId": oid,
        "hoTen": ho_ten,
        "soDienThoai": so_dien_thoai,
        "diaChi": dia_chi,
        "ngayGiao": ngay_giao,
        "ghiChu": ghi_chu,
        "phuongThucThanhToan": phuong_thuc,
        "trangThai": "cho_xu_ly",
        "ngayTao": timezone.now(),
        "tongTien": 0,  # bạn tính lại tổng tiền
    }
    res = donhang.insert_one(order_doc)

    return redirect("shop:orders_index")