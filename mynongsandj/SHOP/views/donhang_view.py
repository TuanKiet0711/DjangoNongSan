# SHOP/views/donhang_view.py
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from functools import wraps
from bson import ObjectId
import json

from ..database import donhang, sanpham, giohang


# ================== Constants / helpers ==================
PAYMENT_METHODS = {"cod", "chuyen_khoan"}
_ALIAS_PM = {
    "ck": "chuyen_khoan", "chuyen-khoan": "chuyen_khoan", "bank": "chuyen_khoan",
    "bank_transfer": "chuyen_khoan", "transfer": "chuyen_khoan",
    "vnpay": "chuyen_khoan", "momo": "chuyen_khoan", "vi_dien_tu": "chuyen_khoan",
}
ORDER_STATUSES = {"cho_xu_ly", "da_xac_nhan", "dang_giao", "hoan_thanh", "da_huy"}


def _pm(v: str) -> str:
    v = (v or "").strip().lower()
    v = _ALIAS_PM.get(v, v)
    return v if v in PAYMENT_METHODS else "cod"


def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def _iso(dt):
    try:
        return timezone.localtime(dt).isoformat()
    except Exception:
        try:
            return dt.isoformat()
        except Exception:
            return str(dt)


def _oid(s):
    try:
        return ObjectId(str(s))
    except Exception:
        return None


def _json_required(request):
    ctype = request.content_type or ""
    if not ctype.startswith("application/json"):
        return JsonResponse({"error": "Content-Type must be application/json"}, status=415)
    return None


# ---------- Auth helpers ----------
def _must_login(request):
    user = request.session.get("user_id")
    try:
        return ObjectId(user) if user else None
    except Exception:
        return None


def require_login_api(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        uid = _must_login(request)
        if not uid:
            return JsonResponse({"error": "not_authenticated"}, status=401)
        request.user_oid = uid
        return view_func(request, *args, **kwargs)
    return _wrapped


# ---------- Cart & Product helpers ----------
def _get_cart_items(uid: ObjectId):
    """
    Chuẩn hoá item giỏ hàng về dạng:
    {sanPhamId:ObjectId, soLuong:int}
    Chấp nhận nhiều key khả dĩ: sanPhamId/product_id/cake_id; quantity/so_luong/soLuong
    """
    rows = list(giohang.find({"taiKhoanId": uid})) or list(giohang.find({"user_id": uid}))
    items = []
    for r in rows:
        pid = r.get("sanPhamId") or r.get("product_id") or r.get("cake_id")
        if not pid:
            continue
        sp_oid = _oid(pid)
        if not sp_oid:
            continue
        qty = r.get("soLuong")
        if qty is None:
            qty = r.get("so_luong", r.get("quantity", 1))
        qty = max(_int(qty, 1), 1)
        items.append({"sanPhamId": sp_oid, "soLuong": qty})
    return items


def _map_product(sp):
    """Chuẩn hoá sản phẩm DB: ưu tiên (ten, gia) – fallback (name, price)"""
    ten = sp.get("ten", sp.get("name", ""))
    gia = _int(sp.get("gia", sp.get("price", 0)), 0)
    return ten, gia


# ---------- Legacy root fields helper (để khớp validator Mongo) ----------
def _apply_legacy_root_fields(doc_or_update: dict):
    """
    Lấy 3 field legacy (sanPhamId, soLuong, donGia) từ items[0]
    và gắn lên cấp root cho phù hợp validator Mongo.
    Dùng cho cả insert (order_doc) và update (update dict).
    """
    items = (doc_or_update or {}).get("items") or []
    if not items:
        return
    first = items[0]
    doc_or_update["sanPhamId"] = first.get("sanPhamId")
    doc_or_update["soLuong"] = _int(first.get("soLuong", 0), 0)
    doc_or_update["donGia"] = _int(first.get("donGia", 0), 0)


# ================= LIST (CHỈ ĐƠN CỦA CHÍNH MÌNH) ==================
@require_http_methods(["GET"])
@require_login_api
def orders_list(request):
    """
    GET /api/orders/?status=<optional>
    Trả danh sách các đơn của chính user đang đăng nhập (schema camelCase).
    """
    status_q = (request.GET.get("status") or "").strip()
    q = {"taiKhoanId": request.user_oid}
    if status_q:
        q["trangThai"] = status_q

    cursor = donhang.find(q).sort("ngayTao", -1)
    items = []
    for d in cursor:
        items.append({
            "id": str(d.get("_id")),
            "taiKhoanId": str(d.get("taiKhoanId")),
            "soLuongSanPham": sum(_int(it.get("soLuong", 0), 0) for it in (d.get("items") or [])),
            "tongTien": _int(d.get("tongTien", 0), 0),
            "trangThai": d.get("trangThai", ""),
            "phuongThucThanhToan": d.get("phuongThucThanhToan", ""),
            "ngayTao": _iso(d.get("ngayTao")),
        })
    return JsonResponse({"items": items})


# ================ CREATE (CHECKOUT API – từ giỏ hoặc buy_now_id) ==================
@csrf_exempt
@require_http_methods(["POST"])
@require_login_api
def orders_checkout(request):
    """
    POST /api/orders/checkout
    Body:
      - Mua ngay: { buyNowProductId, buyNowQuantity, shipping{...}, paymentMethod }
      - Từ giỏ:   { shipping{...}, paymentMethod } (không gửi buyNowProductId)
    """
    err = _json_required(request)
    if err:
        return err

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    buyNowProductId = data.get("buyNowProductId")
    buyNowQuantity = data.get("buyNowQuantity")
    shipping = data.get("shipping", {}) or {}
    paymentMethod = _pm(data.get("paymentMethod", "cod"))

    items = []
    tong_tien = 0

    # Mua ngay 1 sản phẩm
    if buyNowProductId:
        sp = sanpham.find_one({"_id": _oid(buyNowProductId)})
        if not sp:
            return JsonResponse({"error": "Sản phẩm không tồn tại"}, status=404)

        so_luong = max(_int(buyNowQuantity, 1), 1)
        ten, don_gia = _map_product(sp)
        thanh_tien = don_gia * so_luong

        items.append({
            "sanPhamId": sp["_id"],
            "tenSanPham": ten,
            "soLuong": so_luong,
            "donGia": don_gia,
            "thanhTien": thanh_tien,
        })
        tong_tien += thanh_tien

    # Thanh toán giỏ hàng
    else:
        cart_items = _get_cart_items(request.user_oid)
        if not cart_items:
            return JsonResponse({"error": "Giỏ hàng rỗng"}, status=400)

        for c in cart_items:
            sp = sanpham.find_one({"_id": c["sanPhamId"]})
            if not sp:
                continue
            ten, don_gia = _map_product(sp)
            so_luong = max(_int(c.get("soLuong", 1), 1), 1)
            thanh_tien = don_gia * so_luong
            items.append({
                "sanPhamId": sp["_id"],
                "tenSanPham": ten,
                "soLuong": so_luong,
                "donGia": don_gia,
                "thanhTien": thanh_tien,
            })
            tong_tien += thanh_tien

        # Xoá giỏ sau khi đặt
        giohang.delete_many({"taiKhoanId": request.user_oid})
        giohang.delete_many({"user_id": request.user_oid})  # fallback schema cũ

    now = timezone.now()
    order_doc = {
        "taiKhoanId": request.user_oid,
        "items": items,
        "shipping": {
            "hoTen": shipping.get("hoTen", ""),
            "soDienThoai": shipping.get("soDienThoai", ""),
            "diaChi": shipping.get("diaChi", ""),
            "ngayGiao": shipping.get("ngayGiao", ""),
            "ghiChu": shipping.get("ghiChu", ""),
        },
        "phuongThucThanhToan": paymentMethod,
        "tongTien": tong_tien,
        "trangThai": "cho_xu_ly",
        "ngayTao": now,            # bsonType: date
        "ngayCapNhat": now,
    }

    # ✅ Đảm bảo khớp validator: copy 3 field lên root
    _apply_legacy_root_fields(order_doc)

    try:
        result = donhang.insert_one(order_doc)
        return JsonResponse({"created": str(result.inserted_id)}, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ================ DETAIL / UPDATE / DELETE ==================
@csrf_exempt
@require_login_api
def order_detail(request, id):
    """
    GET    /api/orders/<id>/
    PUT    /api/orders/<id>/   (sửa: items[], trangThai, phuongThucThanhToan, shipping)
    DELETE /api/orders/<id>/
    """
    oid = _oid(id)
    if not oid:
        return JsonResponse({"error": "invalid_id"}, status=400)

    d = donhang.find_one({"_id": oid})
    if not d:
        return JsonResponse({"error": "not_found"}, status=404)
    if d.get("taiKhoanId") != request.user_oid:
        return JsonResponse({"error": "forbidden"}, status=403)

    if request.method == "GET":
        def _map_item(it):
            return {
                "sanPhamId": str(it.get("sanPhamId")),
                "tenSanPham": it.get("tenSanPham", ""),
                "soLuong": _int(it.get("soLuong", 0), 0),
                "donGia": _int(it.get("donGia", 0), 0),
                "thanhTien": _int(it.get("thanhTien", 0), 0),
            }

        shipping = d.get("shipping", {}) or {}
        return JsonResponse({
            "id": str(d["_id"]),
            "taiKhoanId": str(d.get("taiKhoanId")),
            "items": [_map_item(it) for it in (d.get("items") or [])],
            "tongTien": _int(d.get("tongTien", 0), 0),
            "trangThai": d.get("trangThai", ""),
            "phuongThucThanhToan": d.get("phuongThucThanhToan", ""),
            "ngayTao": _iso(d.get("ngayTao")),
            "ngayCapNhat": _iso(d.get("ngayCapNhat")) if d.get("ngayCapNhat") else None,
            "shipping": {
                "hoTen": shipping.get("hoTen", ""),
                "soDienThoai": shipping.get("soDienThoai", ""),
                "diaChi": shipping.get("diaChi", ""),
                "ngayGiao": shipping.get("ngayGiao", ""),
                "ghiChu": shipping.get("ghiChu", ""),
            }
        })

    if request.method == "PUT":
        err = _json_required(request)
        if err:
            return err
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "invalid_json"}, status=400)

        update = {}

        # Trạng thái (validate enum)
        if "trangThai" in body:
            st = (body.get("trangThai") or "").strip()
            if st and st not in ORDER_STATUSES:
                return JsonResponse({"error": "trangThai_khong_hop_le"}, status=400)
            if st:
                update["trangThai"] = st

        # PM alias
        if "phuongThucThanhToan" in body:
            update["phuongThucThanhToan"] = _pm(body.get("phuongThucThanhToan"))

        # Shipping merge
        shipping = body.get("shipping")
        if isinstance(shipping, dict):
            new_shipping = d.get("shipping", {}) or {}
            new_shipping.update({
                "hoTen": shipping.get("hoTen", new_shipping.get("hoTen", "")),
                "soDienThoai": shipping.get("soDienThoai", new_shipping.get("soDienThoai", "")),
                "diaChi": shipping.get("diaChi", new_shipping.get("diaChi", "")),
                "ngayGiao": shipping.get("ngayGiao", new_shipping.get("ngayGiao", "")),
                "ghiChu": shipping.get("ghiChu", new_shipping.get("ghiChu", "")),
            })
            update["shipping"] = new_shipping

        # Replace toàn bộ items (nếu gửi)
        new_items = body.get("items")
        if isinstance(new_items, list):
            items_doc = []
            for it in new_items:
                sp_id_raw = it.get("sanPhamId")
                sp_oid = _oid(sp_id_raw)
                if not sp_oid:
                    continue
                sp = sanpham.find_one({"_id": sp_oid})
                if not sp:
                    continue
                sl = max(_int(it.get("soLuong", 0), 0), 1)
                ten, gia_db = _map_product(sp)
                dg = max(_int(it.get("donGia", gia_db), 0), 0)
                items_doc.append({
                    "sanPhamId": sp["_id"],
                    "tenSanPham": ten,
                    "soLuong": sl,
                    "donGia": dg,
                    "thanhTien": sl * dg,
                })
            if not items_doc:
                return JsonResponse({"error": "items_empty"}, status=400)
            update["items"] = items_doc
            update["tongTien"] = sum(_int(x["thanhTien"], 0) for x in items_doc)

            # ✅ Cập nhật 3 field legacy lên root để không vi phạm validator
            _apply_legacy_root_fields(update)

        if update:
            update["ngayCapNhat"] = timezone.now()
            donhang.update_one({"_id": oid}, {"$set": update})

        return JsonResponse({"updated": True})

    if request.method == "DELETE":
        deleted = donhang.delete_one({"_id": oid})
        if deleted.deleted_count == 0:
            return JsonResponse({"error": "not_found"}, status=404)
        return HttpResponse(status=204)

    return HttpResponseNotAllowed(["GET", "PUT", "DELETE"])
