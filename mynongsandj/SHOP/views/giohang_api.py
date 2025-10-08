# shop/views/giohang_api.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from bson import ObjectId
from ..database import giohang, sanpham  # Mongo collections

# ------------------ helpers ------------------

def _require_login(request):
    user_str = request.session.get("user_id")
    if not user_str:
        return None, JsonResponse({"error": "not_authenticated"}, status=401)
    try:
        return ObjectId(user_str), None
    except Exception:
        return None, JsonResponse({"error": "invalid_user"}, status=400)

def _totals(user_oid):
    """Tính tổng số lượng và tiền trong giỏ hàng."""
    total_qty = 0
    total_money = 0
    for row in giohang.find({"taiKhoanId": user_oid}):
        total_qty += int(row.get("soLuong", 0))
        total_money += int(row.get("tongTien", 0))
    return total_qty, total_money

# ------------------ APIs ------------------

@require_GET
def api_cart_badge(request):
    """GET /api/cart/badge/ -> {count, total} (chưa login trả 0)."""
    user_str = request.session.get("user_id")
    if not user_str:
        return JsonResponse({"count": 0, "total": 0})
    try:
        user_oid = ObjectId(user_str)
    except Exception:
        return JsonResponse({"count": 0, "total": 0})

    count, total = _totals(user_oid)
    return JsonResponse({"count": count, "total": total})

@require_POST
def api_add_to_cart(request, sp_id):
    """POST /api/cart/add/<sp_id>/"""
    user_oid, err = _require_login(request)
    if err:
        return err

    try:
        sp_oid = ObjectId(sp_id)
    except Exception:
        return JsonResponse({"error": "invalid_product"}, status=400)

    try:
        qty = int((request.POST.get("so_luong") or "1").strip())
        if qty < 1:
            qty = 1
    except Exception:
        qty = 1

    sp = sanpham.find_one({"_id": sp_oid}, {"gia": 1})
    if not sp:
        return JsonResponse({"error": "product_not_found"}, status=404)

    don_gia = int(sp.get("gia", 0))
    row = giohang.find_one({"taiKhoanId": user_oid, "sanPhamId": sp_oid})

    if row:
        new_qty = int(row.get("soLuong", 0)) + qty
        giohang.update_one(
            {"_id": row["_id"]},
            {"$set": {
                "soLuong": new_qty,
                "donGia": don_gia,
                "tongTien": don_gia * new_qty,
                "ngayCapNhat": timezone.now()
            }}
        )
    else:
        giohang.insert_one({
            "taiKhoanId": user_oid,
            "sanPhamId": sp_oid,
            "soLuong": qty,
            "donGia": don_gia,
            "tongTien": don_gia * qty,
            "ngayTao": timezone.now(),
            "ngayCapNhat": timezone.now()
        })

    count, total = _totals(user_oid)
    return JsonResponse({"success": True, "count": count, "total": total})

# ✅ Endpoint chính để checkout.html gọi
@require_GET
def api_cart(request):
    """
    GET /api/cart/?include_product=1
    Trả về danh sách chi tiết giỏ hàng + tổng tiền.
    """
    user_oid, err = _require_login(request)
    if err:
        return err

    include_product = request.GET.get("include_product")
    items = []
    total_money = 0

    for row in giohang.find({"taiKhoanId": user_oid}):
        sp_data = {}
        if include_product:
            sp = sanpham.find_one({"_id": row["sanPhamId"]}, {"tenSanPham": 1, "gia": 1, "hinhAnh": 1})
            if sp:
                sp_data = {
                    "id": str(sp["_id"]),
                    "tenSanPham": sp.get("tenSanPham", ""),
                    "gia": int(sp.get("gia", 0)),
                    "hinhAnh": (sp.get("hinhAnh") or ["/static/img/no-image.png"])[0],
                }

        item = {
            "san_pham": sp_data,
            "soLuong": int(row.get("soLuong", 0)),
            "thanhTien": int(row.get("tongTien", 0)),
        }
        total_money += item["thanhTien"]
        items.append(item)

    return JsonResponse({"items": items, "total": total_money})

@require_GET
def api_cart_list(request):
    """GET /api/cart/list/ -> {success, items[], count, total}"""
    user_oid, err = _require_login(request)
    if err:
        return err

    items = []
    cursor = giohang.find({"taiKhoanId": user_oid})
    for row in cursor:
        sp = sanpham.find_one({"_id": row["sanPhamId"]}, {"tenSanPham": 1, "hinhAnh": 1})
        items.append({
            "id": str(row["sanPhamId"]),
            "name": (sp.get("tenSanPham") if sp else "Sản phẩm"),
            "image": ((sp.get("hinhAnh") or [""])[0] if sp else ""),
            "price": int(row.get("donGia", 0)),
            "qty": int(row.get("soLuong", 0)),
            "subtotal": int(row.get("tongTien", 0)),
        })

    count, total = _totals(user_oid)
    return JsonResponse({"success": True, "items": items, "count": count, "total": total})

@require_POST
def api_cart_update(request, sp_id):
    """POST /api/cart/update/<sp_id>/"""
    user_oid, err = _require_login(request)
    if err:
        return err

    try:
        sp_oid = ObjectId(sp_id)
    except Exception:
        return JsonResponse({"error": "invalid_product"}, status=400)

    try:
        qty = int(request.POST.get("qty", ""))
    except Exception:
        return JsonResponse({"error": "qty_invalid"}, status=400)

    row = giohang.find_one({"taiKhoanId": user_oid, "sanPhamId": sp_oid})
    if not row:
        return JsonResponse({"error": "not_found"}, status=404)

    if qty <= 0:
        giohang.delete_one({"_id": row["_id"]})
    else:
        don_gia = int(row.get("donGia", 0))
        giohang.update_one(
            {"_id": row["_id"]},
            {"$set": {
                "soLuong": qty,
                "tongTien": don_gia * qty,
                "ngayCapNhat": timezone.now()
            }}
        )

    count, total = _totals(user_oid)
    return JsonResponse({"success": True, "count": count, "total": total})

@require_POST
def api_cart_remove(request, sp_id):
    """POST /api/cart/remove/<sp_id>/"""
    user_oid, err = _require_login(request)
    if err:
        return err

    try:
        sp_oid = ObjectId(sp_id)
    except Exception:
        return JsonResponse({"error": "invalid_product"}, status=400)

    giohang.delete_one({"taiKhoanId": user_oid, "sanPhamId": sp_oid})

    count, total = _totals(user_oid)
    return JsonResponse({"success": True, "count": count, "total": total})

@require_POST
def api_cart_clear(request):
    """POST /api/cart/clear/"""
    user_oid, err = _require_login(request)
    if err:
        return err

    giohang.delete_many({"taiKhoanId": user_oid})
    return JsonResponse({"success": True, "count": 0, "total": 0})
