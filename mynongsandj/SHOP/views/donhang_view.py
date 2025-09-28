# shop/views/donhang_view.py
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from bson import ObjectId
from django.shortcuts import render, redirect
from django.utils import timezone
from ..database import donhang, sanpham

import json

# ================= LIST ==================
@require_http_methods(["GET"])
def orders_list(request):
    """
    GET /api/orders/?user_id=
    """
    user_id = request.GET.get("user_id")
    filter_ = {}
    if user_id:
        try:
            filter_["taiKhoanId"] = ObjectId(user_id)
        except Exception:
            return JsonResponse({"error": "Invalid user_id"}, status=400)

    cursor = donhang.find(filter_).sort("ngayTao", -1)
    items = []
    for d in cursor:
        items.append({
            "id": str(d["_id"]),
            "taiKhoanId": str(d["taiKhoanId"]),
            "sanPhamId": str(d["sanPhamId"]),
            "soLuong": d.get("soLuong", 0),
            "donGia": d.get("donGia", 0),
            "tongTien": d.get("tongTien", 0),
            "trangThai": d.get("trangThai", ""),
            "phuongThucThanhToan": d.get("phuongThucThanhToan", ""),
            "ngayTao": str(d.get("ngayTao", "")),
        })
    return JsonResponse({"items": items})


# ================ CREATE ==================
@csrf_exempt
@require_http_methods(["POST"])
def order_create(request):
    """
    POST /api/orders/
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        doc = {
            "taiKhoanId": ObjectId(body["taiKhoanId"]),
            "sanPhamId": ObjectId(body["sanPhamId"]),
            "soLuong": int(body.get("soLuong", 1)),
            "donGia": int(body.get("donGia", 0)),
            "tongTien": int(body.get("tongTien", 0)),
            "phuongThucThanhToan": body.get("phuongThucThanhToan", "cod"),
            "trangThai": "cho_xu_ly",
        }
    except Exception as e:
        return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)

    res = donhang.insert_one(doc)
    return JsonResponse({"id": str(res.inserted_id)}, status=201)


# ================ DETAIL ==================
@csrf_exempt
def order_detail(request, id):
    """
    GET /api/orders/<id>/
    PUT /api/orders/<id>/
    DELETE /api/orders/<id>/
    """
    try:
        oid = ObjectId(id)
    except Exception:
        return JsonResponse({"error": "Invalid id"}, status=400)

    if request.method == "GET":
        d = donhang.find_one({"_id": oid})
        if not d:
            return JsonResponse({"error": "Not found"}, status=404)
        return JsonResponse({
            "id": str(d["_id"]),
            "taiKhoanId": str(d["taiKhoanId"]),
            "sanPhamId": str(d["sanPhamId"]),
            "soLuong": d.get("soLuong", 0),
            "donGia": d.get("donGia", 0),
            "tongTien": d.get("tongTien", 0),
            "trangThai": d.get("trangThai", ""),
            "phuongThucThanhToan": d.get("phuongThucThanhToan", ""),
            "ngayTao": str(d.get("ngayTao", "")),
        })

    elif request.method == "PUT":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        update = {}
        for f in ["soLuong", "donGia", "tongTien", "trangThai", "phuongThucThanhToan"]:
            if f in body:
                update[f] = body[f]

        if update:
            donhang.update_one({"_id": oid}, {"$set": update})
        return JsonResponse({"updated": True})

    elif request.method == "DELETE":
        deleted = donhang.delete_one({"_id": oid})
        if deleted.deleted_count == 0:
            return JsonResponse({"error": "Not found"}, status=404)
        return HttpResponse(status=204)

    else:
        return HttpResponseNotAllowed(["GET", "PUT", "DELETE"])


def _get_or_create_cart(user_oid):
    """Lấy hoặc tạo đơn 'cart' (giỏ hàng) cho user."""
    cart = donhang.find_one({"taiKhoanId": user_oid, "trangThai": "cart"})
    if not cart:
        cart = {
            "taiKhoanId": user_oid,
            "trangThai": "cart",          # đơn giỏ hàng
            "items": [],                  # mảng sản phẩm trong giỏ
            "tongTien": 0,
            "ngayTao": timezone.now(),
            "ngayCapNhat": timezone.now(),
        }
        res = donhang.insert_one(cart)
        cart["_id"] = res.inserted_id
    return cart

@csrf_exempt
def api_add_to_cart(request, sp_id):
    """
    POST /api/cart/add/<sp_id>/
    Body (optional): so_luong=1
    -> Lưu vào 1 đơn 'cart' có nhiều sản phẩm
    """
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    user_str = request.session.get("user_id")
    if not user_str:
        # Chưa login
        return JsonResponse({"error": "not_authenticated"}, status=401)

    try:
        user_oid = ObjectId(user_str)
        sp_oid = ObjectId(sp_id)
    except Exception:
        return JsonResponse({"error": "invalid_id"}, status=400)

    qty = 1
    try:
        qty = int((request.POST.get("so_luong") or "1").strip())
        if qty < 1: qty = 1
    except Exception:
        qty = 1

    sp = sanpham.find_one({"_id": sp_oid}, {"tenSanPham":1, "gia":1, "hinhAnh":1})
    if not sp:
        return JsonResponse({"error": "product_not_found"}, status=404)

    don_gia = int(sp.get("gia", 0))
    cart = _get_or_create_cart(user_oid)
    items = cart.get("items", [])

    # Tìm xem sản phẩm đã có trong giỏ chưa
    found = False
    for it in items:
        if it.get("sanPhamId") == sp_oid:
            it["soLuong"] = int(it.get("soLuong", 0)) + qty
            it["donGia"] = don_gia
            it["thanhTien"] = int(it["soLuong"]) * int(it["donGia"])
            found = True
            break

    if not found:
        items.append({
            "sanPhamId": sp_oid,
            "tenSanPham": sp.get("tenSanPham") or "",
            "hinhAnh": (sp.get("hinhAnh") or [""])[0],
            "donGia": don_gia,
            "soLuong": qty,
            "thanhTien": don_gia * qty
        })

    tong_tien = sum(int(i.get("thanhTien", 0)) for i in items)

    donhang.update_one(
        {"_id": cart["_id"]},
        {"$set": {
            "items": items,
            "tongTien": tong_tien,
            "ngayCapNhat": timezone.now()
        }}
    )

    total_items = sum(int(i.get("soLuong", 0)) for i in items)
    return JsonResponse({"success": True, "count": total_items, "total": tong_tien})

def api_cart_badge(request):
    """GET /api/cart/badge/ -> trả số lượng item & tổng tiền trong giỏ"""
    user_str = request.session.get("user_id")
    if not user_str:
        return JsonResponse({"count": 0, "total": 0})

    try:
        cart = donhang.find_one({"taiKhoanId": ObjectId(user_str), "trangThai": "cart"})
    except Exception:
        cart = None

    if not cart:
        return JsonResponse({"count": 0, "total": 0})

    count = sum(int(i.get("soLuong", 0)) for i in cart.get("items", []))
    total = int(cart.get("tongTien", 0))
    return JsonResponse({"count": count, "total": total})