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
    rows = list(giohang.find({"taiKhoanId": uid})) or list(giohang.find({"user_id": uid}))
    items = []
    for r in rows:
        pid = r.get("sanPhamId") or r.get("product_id")
        if not pid:
            continue
        sp_oid = _oid(pid)
        if not sp_oid:
            continue
        qty = _int(r.get("soLuong") or r.get("quantity") or 1, 1)
        items.append({"sanPhamId": sp_oid, "soLuong": qty})
    return items

def _map_product(sp):
    ten = sp.get("tenSanPham") or sp.get("ten") or sp.get("name", "")
    gia = _int(sp.get("gia", sp.get("price", 0)), 0)
    hinh = sp.get("hinhAnh")
    if isinstance(hinh, list) and hinh:
        hinh = hinh[0]
    elif isinstance(hinh, str):
        pass
    else:
        hinh = "/static/img/no-image.png"
    return ten, gia, hinh

def _apply_legacy_root_fields(doc):
    items = doc.get("items") or []
    if not items:
        return
    f = items[0]
    doc["sanPhamId"] = f.get("sanPhamId")
    doc["soLuong"] = _int(f.get("soLuong", 0))
    doc["donGia"] = _int(f.get("donGia", 0))

# ================= LIST (MY ORDERS) ==================
@require_http_methods(["GET"])
@require_login_api
def orders_list(request):
    status_q = (request.GET.get("status") or "").strip()
    q = {"taiKhoanId": request.user_oid}
    if status_q:
        q["trangThai"] = status_q

    cursor = donhang.find(q).sort("ngayTao", -1)
    items = []
    for d in cursor:
        items.append({
            "id": str(d["_id"]),
            "tongTien": _int(d.get("tongTien", 0)),
            "trangThai": d.get("trangThai", ""),
            "phuongThucThanhToan": d.get("phuongThucThanhToan", ""),
            "ngayTao": _iso(d.get("ngayTao")),
            "items": [
                {
                    "sanPhamId": str(it.get("sanPhamId")),
                    "tenSanPham": it.get("tenSanPham", ""),
                    "hinhAnh": it.get("hinhAnh", ""),
                    "soLuong": _int(it.get("soLuong", 0)),
                    "donGia": _int(it.get("donGia", 0)),
                    "thanhTien": _int(it.get("thanhTien", 0)),
                }
                for it in (d.get("items") or [])
            ],
        })
    return JsonResponse({"items": items}, json_dumps_params={"ensure_ascii": False})


# ================ CHECKOUT ==================
@csrf_exempt
@require_http_methods(["POST"])
@require_login_api
def orders_checkout(request):
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

    # --- mua ngay ---
    if buyNowProductId:
        sp = sanpham.find_one({"_id": _oid(buyNowProductId)})
        if not sp:
            return JsonResponse({"error": "product_not_found"}, status=404)
        so_luong = max(_int(buyNowQuantity, 1), 1)
        ten, don_gia, hinh = _map_product(sp)
        tt = don_gia * so_luong
        items.append({
            "sanPhamId": sp["_id"],
            "tenSanPham": ten,
            "hinhAnh": hinh,
            "soLuong": so_luong,
            "donGia": don_gia,
            "thanhTien": tt,
        })
        tong_tien += tt
    else:
        # --- từ giỏ ---
        cart_items = _get_cart_items(request.user_oid)
        if not cart_items:
            return JsonResponse({"error": "cart_empty"}, status=400)
        for c in cart_items:
            sp = sanpham.find_one({"_id": c["sanPhamId"]})
            if not sp:
                continue
            ten, don_gia, hinh = _map_product(sp)
            sl = max(_int(c.get("soLuong", 1)), 1)
            tt = don_gia * sl
            items.append({
                "sanPhamId": sp["_id"],
                "tenSanPham": ten,
                "hinhAnh": hinh,
                "soLuong": sl,
                "donGia": don_gia,
                "thanhTien": tt,
            })
            tong_tien += tt
        giohang.delete_many({"taiKhoanId": request.user_oid})

    now = timezone.now()
    doc = {
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
        "ngayTao": now,
        "ngayCapNhat": now,
    }
    _apply_legacy_root_fields(doc)
    result = donhang.insert_one(doc)
    return JsonResponse({"created": str(result.inserted_id)}, status=201)


# ================ DETAIL / UPDATE / DELETE ==================
@csrf_exempt
@require_login_api
def order_detail(request, id):
    oid = _oid(id)
    if not oid:
        return JsonResponse({"error": "invalid_id"}, status=400)
    d = donhang.find_one({"_id": oid})
    if not d:
        return JsonResponse({"error": "not_found"}, status=404)
    if d.get("taiKhoanId") != request.user_oid:
        return JsonResponse({"error": "forbidden"}, status=403)

    # ----- GET -----
    if request.method == "GET":
        ship = d.get("shipping", {}) or {}
        return JsonResponse({
            "id": str(d["_id"]),
            "tongTien": _int(d.get("tongTien", 0)),
            "trangThai": d.get("trangThai", ""),
            "phuongThucThanhToan": d.get("phuongThucThanhToan", ""),
            "ngayTao": _iso(d.get("ngayTao")),
            "items": [
                {
                    "sanPhamId": str(it.get("sanPhamId")),
                    "tenSanPham": it.get("tenSanPham", ""),
                    "hinhAnh": it.get("hinhAnh", ""),
                    "soLuong": _int(it.get("soLuong", 0)),
                    "donGia": _int(it.get("donGia", 0)),
                    "thanhTien": _int(it.get("thanhTien", 0)),
                } for it in (d.get("items") or [])
            ],
            "shipping": ship,
        }, json_dumps_params={"ensure_ascii": False})

    # ----- PUT (update hoặc hủy) -----
    if request.method == "PUT":
        err = _json_required(request)
        if err:
            return err
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "invalid_json"}, status=400)

        update = {}
        if "trangThai" in body:
            st = body.get("trangThai")
            if st == "da_huy":
                # chỉ cho phép huỷ khi chưa giao
                if d.get("trangThai") not in ("cho_xu_ly", "da_xac_nhan"):
                    return JsonResponse({"error": "cannot_cancel"}, status=400)
                update["trangThai"] = "da_huy"
            elif st in ORDER_STATUSES:
                update["trangThai"] = st

        if update:
            update["ngayCapNhat"] = timezone.now()
            donhang.update_one({"_id": oid}, {"$set": update})
            return JsonResponse({"updated": True})
        return JsonResponse({"error": "no_fields"}, status=400)

    # ----- DELETE -----
    if request.method == "DELETE":
        donhang.delete_one({"_id": oid})
        return HttpResponse(status=204)

    return HttpResponseNotAllowed(["GET", "PUT", "DELETE"])
