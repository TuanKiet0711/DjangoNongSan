# shop/views/sanpham_view.py
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http.multipartparser import MultiPartParser
from bson import ObjectId
from ..database import sanpham as san_pham, danhmuc

import os, json

PAGE_SIZE_DEFAULT = 6
PAGE_SIZE_MAX = 100

# ---------- Utils ----------
def _save_product_file(fileobj):
    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "sanpham"))
    filename = fs.save(fileobj.name, fileobj)
    return "sanpham/" + filename

def _as_oid(val):
    if not val:
        return None
    try:
        return ObjectId(val)
    except Exception:
        return None

def _ok_json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})

def _json_required(request):
    ctype = request.content_type or ""
    if not ctype.startswith("application/json"):
        return JsonResponse({"error": "Content-Type must be application/json"}, status=415)
    return None

def _pick(data, *names):
    return {k: data.get(k) for k in names if k in data}

def _get_val(body, *keys, default=None, cast=None):
    for k in keys:
        if k in body and body[k] is not None:
            v = body[k]
            if cast:
                try:
                    v = cast(v)
                except Exception:
                    raise
            return v
    return default

def _product_to_snake(sp):
    """Chuẩn hóa document Mongo -> JSON snake_case cho FE admin."""
    return {
        "id": str(sp.get("_id")),
        "ten_san_pham": sp.get("tenSanPham", ""),
        "mo_ta": sp.get("moTa", ""),
        "gia": int(sp.get("gia", 0)),
        "hinh_anh": sp.get("hinhAnh", []),
        "danh_muc_id": str(sp.get("danhMucId")) if sp.get("danhMucId") else None,
        # NEW: tồn kho
        "so_luong_ton": int(sp.get("soLuongTon", 0)),
    }

# ================= LIST ==================
@require_http_methods(["GET"])
def products_list(request):
    """
    GET /api/products/?q=&page=&page_size=
    """
    q = (request.GET.get("q") or "").strip()
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        page_size = min(max(int(request.GET.get("page_size", PAGE_SIZE_DEFAULT)), 1), PAGE_SIZE_MAX)
    except ValueError:
        page_size = PAGE_SIZE_DEFAULT

    filter_ = {}
    if q:
        filter_["tenSanPham"] = {"$regex": q, "$options": "i"}

    total = san_pham.count_documents(filter_)
    skip = (page - 1) * page_size

    cursor = (
        san_pham.find(
            filter_,
            {"tenSanPham": 1, "gia": 1, "hinhAnh": 1, "danhMucId": 1, "moTa": 1, "soLuongTon": 1}  # NEW
        )
        .sort("_id", -1) 
        .skip(skip)
        .limit(page_size)
    )

    items = [_product_to_snake(sp) for sp in cursor]

    return _ok_json({
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    })

# ================ CREATE ==================
@csrf_exempt
@require_http_methods(["POST"])
def products_create(request):
    """
    POST /api/products/
    Hỗ trợ multipart/form-data và JSON.
    """
    if (request.content_type or "").startswith("multipart/form-data"):
        ten = (request.POST.get("ten_san_pham") or request.POST.get("tenSanPham") or "").strip()
        mo_ta = (request.POST.get("mo_ta") or request.POST.get("moTa") or "").strip()
        danh_muc_id = request.POST.get("danh_muc_id") or request.POST.get("danhMucId")
        try:
            gia = int(request.POST.get("gia") or 0)
        except Exception:
            return JsonResponse({"error": "gia phải là số"}, status=400)

        # NEW: tồn kho
        try:
            so_luong_ton = int(request.POST.get("so_luong_ton") or request.POST.get("soLuongTon") or 0)
        except Exception:
            so_luong_ton = 0

        hinh_anh_urls = []
        if "hinh_anh" in request.FILES or "hinhAnh" in request.FILES:
            file = request.FILES.get("hinh_anh") or request.FILES.get("hinhAnh")
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "sanpham"))
            filename = fs.save(file.name, file)
            hinh_anh_urls.append("sanpham/" + filename)

        doc = {
            "tenSanPham": ten,
            "moTa": mo_ta,
            "gia": gia,
            "hinhAnh": hinh_anh_urls,
            "soLuongTon": so_luong_ton,  # NEW
        }
        if danh_muc_id:
            oid = _as_oid(danh_muc_id)
            if not oid:
                return JsonResponse({"error": "Invalid danh_muc_id"}, status=400)
            doc["danhMucId"] = oid

        res = san_pham.insert_one(doc)
        created = san_pham.find_one({"_id": res.inserted_id})
        return _ok_json(_product_to_snake(created), status=201)

    # JSON
    err = _json_required(request)
    if err:
        return err
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ten = (_get_val(body, "ten_san_pham", "tenSanPham", default="") or "").strip()
    mo_ta = (_get_val(body, "mo_ta", "moTa", default="") or "").strip()
    gia_raw = _get_val(body, "gia", default=0)
    hinh_anh = _get_val(body, "hinh_anh", "hinhAnh", default=[]) or []
    danh_muc_id = _get_val(body, "danh_muc_id", "danhMucId")
    so_luong_ton_raw = _get_val(body, "so_luong_ton", "soLuongTon", default=0)  # NEW

    if not ten:
        return JsonResponse({"error": "Thiếu ten_san_pham"}, status=400)

    try:
        gia = int(gia_raw or 0)
    except Exception:
        return JsonResponse({"error": "gia phải là số"}, status=400)

    try:
        so_luong_ton = int(so_luong_ton_raw or 0)  # NEW
    except Exception:
        so_luong_ton = 0

    doc = {
        "tenSanPham": ten,
        "moTa": mo_ta,
        "gia": gia,
        "hinhAnh": hinh_anh if isinstance(hinh_anh, list) else [hinh_anh],
        "soLuongTon": so_luong_ton,  # NEW
    }
    if danh_muc_id:
        oid = _as_oid(danh_muc_id)
        if not oid:
            return JsonResponse({"error": "Invalid danh_muc_id"}, status=400)
        doc["danhMucId"] = oid

    res = san_pham.insert_one(doc)
    created = san_pham.find_one({"_id": res.inserted_id})
    return _ok_json(_product_to_snake(created), status=201)

# ================ DETAIL (GET/PUT/DELETE) ==================
@csrf_exempt
def product_detail(request, id):
    """
    GET /api/products/<id>/
    PUT /api/products/<id>/
    DELETE /api/products/<id>/
    """
    oid = _as_oid(id)
    if not oid:
        return JsonResponse({"error": "Invalid id"}, status=400)

    # ---------- GET ----------
    if request.method == "GET":
        sp = san_pham.find_one({"_id": oid})
        if not sp:
            return JsonResponse({"error": "Not found"}, status=404)

        return JsonResponse({
            "id": str(sp.get("_id")),
            "tenSanPham": sp.get("tenSanPham") or sp.get("ten") or sp.get("name", ""),
            "moTa": sp.get("moTa", ""),
            "gia": int(sp.get("gia", 0)),
            "hinhAnh": sp.get("hinhAnh", []),
            "danhMucId": str(sp.get("danhMucId")) if sp.get("danhMucId") else None,
            "soLuongTon": int(sp.get("soLuongTon", 0)),  # NEW
        }, json_dumps_params={"ensure_ascii": False})

    # ---------- PUT ----------
    elif request.method == "PUT":
        ctype = (request.content_type or "").lower()
        update = {}
        if ctype.startswith("multipart/form-data"):
            try:
                parser = MultiPartParser(request.META, request, request.upload_handlers, request.encoding)
                data, files = parser.parse()
            except Exception:
                return JsonResponse({"error": "parse_multipart_failed"}, status=400)

            ten = (data.get("ten_san_pham") or data.get("tenSanPham") or "").strip()
            mo_ta = (data.get("mo_ta") or data.get("moTa") or "").strip()
            gia_raw = data.get("gia")
            danh_muc_id = data.get("danh_muc_id") or data.get("danhMucId")
            so_luong_ton_raw = data.get("so_luong_ton") or data.get("soLuongTon")  # NEW

            if ten:
                update["tenSanPham"] = ten
            if mo_ta:
                update["moTa"] = mo_ta
            if gia_raw is not None:
                try:
                    update["gia"] = int(gia_raw)
                except:
                    return JsonResponse({"error": "gia phải là số"}, status=400)
            if danh_muc_id:
                oid_dm = _as_oid(danh_muc_id)
                if oid_dm:
                    update["danhMucId"] = oid_dm
            if so_luong_ton_raw is not None:  # NEW
                try:
                    update["soLuongTon"] = int(so_luong_ton_raw)
                except:
                    return JsonResponse({"error": "so_luong_ton phải là số"}, status=400)

            file_obj = files.get("hinh_anh") or files.get("hinhAnh")
            if file_obj:
                saved = _save_product_file(file_obj)
                update["hinhAnh"] = [saved]

        else:
            err = _json_required(request)
            if err:
                return err
            try:
                body = json.loads(request.body.decode("utf-8"))
            except Exception:
                return JsonResponse({"error": "Invalid JSON"}, status=400)

            if "ten_san_pham" in body or "tenSanPham" in body:
                update["tenSanPham"] = _get_val(body, "ten_san_pham", "tenSanPham", default="")
            if "mo_ta" in body or "moTa" in body:
                update["moTa"] = _get_val(body, "mo_ta", "moTa", default="")
            if "gia" in body:
                try:
                    update["gia"] = int(body.get("gia") or 0)
                except:
                    return JsonResponse({"error": "gia phải là số"}, status=400)
            if "hinh_anh" in body or "hinhAnh" in body:
                ha = _get_val(body, "hinh_anh", "hinhAnh", default=[])
                update["hinhAnh"] = ha if isinstance(ha, list) else [ha]
            if "danh_muc_id" in body or "danhMucId" in body:
                dm = _get_val(body, "danh_muc_id", "danhMucId")
                oid_dm = _as_oid(dm)
                if oid_dm:
                    update["danhMucId"] = oid_dm
            if "so_luong_ton" in body or "soLuongTon" in body:  # NEW
                try:
                    update["soLuongTon"] = int(_get_val(body, "so_luong_ton", "soLuongTon", default=0))
                except:
                    return JsonResponse({"error": "so_luong_ton phải là số"}, status=400)

        if not update:
            return JsonResponse({"error": "No fields to update"}, status=400)

        san_pham.update_one({"_id": oid}, {"$set": update})
        sp = san_pham.find_one({"_id": oid})
        return _ok_json(_product_to_snake(sp))

    # ---------- DELETE ----------
    elif request.method == "DELETE":
        deleted = san_pham.delete_one({"_id": oid})
        if deleted.deleted_count == 0:
            return JsonResponse({"error": "Not found"}, status=404)
        return HttpResponse(status=204)

    return HttpResponseNotAllowed(["GET", "PUT", "DELETE"])

# ============ ADMIN PANEL VIEWS ============
def _categories_for_select():
    cats = []
    for c in danhmuc.find({}).sort("tenDanhMuc", 1):
        cats.append({"id": str(c["_id"]), "ten": c.get("tenDanhMuc", "Danh mục")})
    return cats

def admin_products_list(request):
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page", 1))
    filter_ = {}
    if q:
        filter_["tenSanPham"] = {"$regex": q, "$options": "i"}

    cursor = san_pham.find(filter_).sort("_id", -1)
    cat_map = {str(c["_id"]): c.get("tenDanhMuc", "") for c in danhmuc.find({})}

    products = []
    for sp in cursor:
        products.append({
            "id": str(sp["_id"]),
            "ten": sp.get("tenSanPham", ""),
            "mo_ta": sp.get("moTa", ""),
            "gia": int(sp.get("gia", 0)),
            "hinh_anh": (sp.get("hinhAnh") or [None])[0] if sp.get("hinhAnh") else None,
            "danh_muc": cat_map.get(str(sp.get("danhMucId")), "Chưa phân loại"),
            "so_luong_ton": int(sp.get("soLuongTon", 0)),  # NEW
        })

    paginator = Paginator(products, 6)
    page_obj = paginator.get_page(page)

    return render(request, "shop/admin/products/products_list.html", {
        "items": page_obj.object_list,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
        "total": paginator.count,
        "has_prev": page_obj.has_previous(),
        "has_next": page_obj.has_next(),
        "page_numbers": paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1),  # type: ignore
        "q": q,
        "placeholders": range(6 - len(page_obj.object_list)),
    })

def product_create(request):
    if request.method == "POST":
        ten = (request.POST.get("ten_san_pham") or request.POST.get("tenSanPham") or "").strip()
        mo_ta = (request.POST.get("mo_ta") or request.POST.get("moTa") or "").strip()
        danh_muc_id = request.POST.get("danh_muc_id") or request.POST.get("danhMucId")
        try:
            gia = int(request.POST.get("gia") or 0)
        except:
            messages.error(request, "Giá phải là số!")
            return redirect("shop:admin_product_create")

        # NEW: nhận tồn kho từ form admin (nếu có)
        try:
            so_luong_ton = int(request.POST.get("so_luong_ton") or request.POST.get("soLuongTon") or 0)
        except:
            so_luong_ton = 0

        doc = {"tenSanPham": ten, "moTa": mo_ta, "gia": gia, "hinhAnh": [], "soLuongTon": so_luong_ton}
        if danh_muc_id:
            oid = _as_oid(danh_muc_id)
            if not oid:
                messages.error(request, "Mã danh mục không hợp lệ")
                return redirect("shop:admin_product_create")
            doc["danhMucId"] = oid

        san_pham.insert_one(doc)
        messages.success(request, "Thêm sản phẩm thành công!")
        return redirect("shop:admin_products")

    return render(request, "shop/admin/products/products_create.html", {
        "categories": _categories_for_select()
    })

def product_edit(request, id):
    oid = _as_oid(id)
    if not oid:
        messages.error(request, "ID sản phẩm không hợp lệ")
        return redirect("shop:admin_products")

    sp = san_pham.find_one({"_id": oid})
    if not sp:
        messages.error(request, "Không tìm thấy sản phẩm")
        return redirect("shop:admin_products")

    return render(request, "shop/admin/products/products_edit.html", {
        "product_id": id,
        "categories": _categories_for_select()
    })

def product_delete(request, id):
    oid = _as_oid(id)
    if not oid:
        messages.error(request, "ID sản phẩm không hợp lệ")
        return redirect("shop:admin_products")

    if request.method == "POST":
        deleted = san_pham.delete_one({"_id": oid})
        if deleted.deleted_count == 0:
            messages.error(request, "Không tìm thấy sản phẩm để xoá")
        else:
            messages.success(request, "Xoá sản phẩm thành công!")
        return redirect("shop:admin_products")

    return render(request, "shop/admin/products/products_delete.html", {"product_id": id})
