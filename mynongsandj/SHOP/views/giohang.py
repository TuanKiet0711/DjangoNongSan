from django.shortcuts import render, redirect
from ..database import giohang, sanpham
from bson import ObjectId

def view_cart(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("shop:auth_login_page")

    oid = ObjectId(user_id)
    items = []
    tong_tien = 0

    for gh in giohang.find({"taiKhoanId": oid}):
        sp = sanpham.find_one({"_id": gh["sanPhamId"]})
        if not sp:
            continue
        item = {
            "tenSanPham": sp.get("tenSanPham"),
            "so_luong": gh.get("soLuong", 0),
            "don_gia": gh.get("donGia", 0),
            "thanh_tien": gh.get("tongTien", 0),
        }
        items.append(item)
        tong_tien += item["thanh_tien"]

    ctx = {"items": items, "tong_tien": tong_tien}
    return render(request, "customer/cart.html", ctx)
