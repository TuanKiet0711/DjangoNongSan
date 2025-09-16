# SHOP/views/danh_muc_view.py
import json
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from ..database import db

# ---------- Helpers ----------
def _col_danhmuc():
    """
    Trả về (collection, storage_field_name)
    - Nếu có 'danh_muc' => dùng field 'ten_danh_muc'
    - Ngược lại dùng 'danhmuc' với field 'tenDanhMuc'
    """
    names = set(db.list_collection_names())
    if "danh_muc" in names:
        col = db["danh_muc"]; field_name = "ten_danh_muc"
    else:
        col = db["danhmuc"];   field_name = "tenDanhMuc"

    # Đảm bảo unique index cho tên (idempotent)
    try:
        col.create_index([(field_name, 1)], unique=True, name=f"uniq_{field_name}")
    except Exception:
        pass
    return col, field_name

def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}

def _extract_name(payload, storage_field):
    """
    Chấp nhận cả hai biến thể: tenDanhMuc hoặc ten_danh_muc.
    Ưu tiên key đúng với storage_field; fallback sang biến thể còn lại.
    """
    alt = "ten_danh_muc" if storage_field == "tenDanhMuc" else "tenDanhMuc"
    return (payload.get(storage_field) or payload.get(alt) or "").strip()

def _safe_object_id(id_str):
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None

# ---------- APIs ----------
@csrf_exempt
def list_danh_muc(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    col, storage_field = _col_danhmuc()
    q = (request.GET.get("q") or "").strip()
    query = {storage_field: {"$regex": q, "$options": "i"}} if q else {}
    docs = list(col.find(query))
    # Luôn chuẩn hoá key trả ra là 'tenDanhMuc'
    items = [{"id": str(d["_id"]), "tenDanhMuc": d.get(storage_field)} for d in docs]
    return JsonResponse({"ok": True, "items": items})

@csrf_exempt
def create_danh_muc(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    col, storage_field = _col_danhmuc()
    data = _json_body(request)
    name = _extract_name(data, storage_field)
    if not name:
        return JsonResponse({"ok": False, "error": "Thiếu tenDanhMuc"}, status=400)
    try:
        inserted_id = col.insert_one({storage_field: name}).inserted_id
    except DuplicateKeyError:
        return JsonResponse({"ok": False, "error": "Danh mục đã tồn tại"}, status=400)
    return JsonResponse({"ok": True, "id": str(inserted_id), "tenDanhMuc": name})

@csrf_exempt
def update_danh_muc(request, id):
    if request.method != "PUT":
        return HttpResponseNotAllowed(["PUT"])
    col, storage_field = _col_danhmuc()
    oid = _safe_object_id(id)
    if not oid:
        return JsonResponse({"ok": False, "error": "ID không hợp lệ"}, status=400)
    data = _json_body(request)
    name = _extract_name(data, storage_field)
    if not name:
        return JsonResponse({"ok": False, "error": "Thiếu tenDanhMuc"}, status=400)
    try:
        result = col.update_one({"_id": oid}, {"$set": {storage_field: name}})
        if result.matched_count == 0:
            return JsonResponse({"ok": False, "error": "Không tìm thấy danh mục"}, status=404)
    except DuplicateKeyError:
        return JsonResponse({"ok": False, "error": "Tên danh mục trùng"}, status=400)
    return JsonResponse({"ok": True, "id": id, "tenDanhMuc": name})

@csrf_exempt
def delete_danh_muc(request, id):
    if request.method != "DELETE":
        return HttpResponseNotAllowed(["DELETE"])
    col, _ = _col_danhmuc()
    oid = _safe_object_id(id)
    if not oid:
        return JsonResponse({"ok": False, "error": "ID không hợp lệ"}, status=400)
    result = col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        return JsonResponse({"ok": False, "error": "Không tìm thấy danh mục"}, status=404)
    return JsonResponse({"ok": True, "deletedId": id})
