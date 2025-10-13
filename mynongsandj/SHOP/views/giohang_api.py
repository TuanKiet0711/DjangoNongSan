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
                # ảnh xử lý đúng đường dẫn
                raw_img = (sp.get("hinhAnh") or ["/static/img/no-image.png"])[0]
                if raw_img.startswith("/media/"):
                    img_url = raw_img
                else:
                    img_url = f"/media/{raw_img.lstrip('/')}"
                sp_data = {
                    "id": str(sp["_id"]),
                    "tenSanPham": sp.get("tenSanPham", ""),
                    "gia": int(sp.get("gia", 0)),
                    "hinhAnh": img_url,
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
    user_str = request.session.get("user_id")
    if not user_str:
        return JsonResponse({"error": "not_authenticated"}, status=401)

    try:
        user_oid = ObjectId(user_str)
    except Exception:
        return JsonResponse({"error": "invalid_user"}, status=400)

    def norm_img(path):
        """Chuẩn hóa đường dẫn ảnh cho mọi kiểu hinhAnh lưu trong MongoDB."""
        if not path:
            return "/static/img/no-image.png"

        path = str(path).strip()

        # Nếu path đã có /media/ ở đầu hoặc chứa 'media/sanpham/' -> giữ nguyên
        if path.startswith("/media/") or "media/sanpham/" in path:
            # đảm bảo có dấu / ở đầu
            if not path.startswith("/"):
                path = "/" + path
            # xóa trường hợp bị lặp /media/media/
            path = path.replace("/media/media/", "/media/")
            return path

        # Nếu có thư mục sanpham mà chưa có /media/
        if "sanpham/" in path:
            return f"/media/{path.lstrip('/')}"

        # Nếu chỉ có tên file
        return f"/media/sanpham/{path.lstrip('/')}"

    items = []
    cursor = giohang.find({"taiKhoanId": user_oid})
    for row in cursor:
        sp = sanpham.find_one({"_id": row["sanPhamId"]}, {"tenSanPham": 1, "hinhAnh": 1})
        ten = sp.get("tenSanPham") if sp else "Sản phẩm"
        raw_img = None
        if sp:
            h = sp.get("hinhAnh")
            if isinstance(h, list) and h:
                raw_img = h[0]
            elif isinstance(h, str):
                raw_img = h
        hinh = norm_img(raw_img)

        don_gia = int(row.get("donGia", 0))
        so_luong = int(row.get("soLuong", 0))
        thanh_tien = int(row.get("tongTien", 0))

        items.append({
            # Cho checkout.html
            "sanPhamId": str(row["sanPhamId"]),
            "tenSanPham": ten,
            "hinhAnh": hinh,
            "soLuong": so_luong,
            "donGia": don_gia,
            "thanhTien": thanh_tien,
            # Cho cart.html
            "id": str(row["sanPhamId"]),
            "name": ten,
            "image": hinh,
            "price": don_gia,
            "qty": so_luong,
            "subtotal": thanh_tien,
        })

    total = sum(x["thanhTien"] for x in items)
    return JsonResponse({"success": True, "items": items, "count": len(items), "total": total})


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
