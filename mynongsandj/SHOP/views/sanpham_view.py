# shop/views/product_api.py
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from bson import ObjectId
from ..database import sanpham as san_pham, danhmuc
from django.core.paginator import Paginator
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os, json

# mặc định 6 sản phẩm / trang
PAGE_SIZE_DEFAULT = 6
PAGE_SIZE_MAX = 100

def _json_required(request):
    ctype = request.content_type or ""
    if not ctype.startswith("application/json"):
        return JsonResponse({"error": "Content-Type must be application/json"}, status=415)
    return None

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

    cursor = (san_pham.find(filter_, {"tenSanPham": 1, "gia": 1, "hinhAnh": 1, "danhMucId": 1})
                      .sort("tenSanPham", 1)
                      .skip(skip)
                      .limit(page_size))

    items = []
    for sp in cursor:
        items.append({
            "id": str(sp["_id"]),
            "tenSanPham": sp.get("tenSanPham", ""),
            "gia": sp.get("gia", 0),
            "hinhAnh": sp.get("hinhAnh", []),
            "danhMucId": str(sp["danhMucId"]) if sp.get("danhMucId") else None
        })

    return JsonResponse({
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
    POST /api/products/  -> tạo sản phẩm mới
    Hỗ trợ multipart/form-data (upload file) hoặc JSON
    """
    # Nếu upload file
    if (request.content_type or "").startswith("multipart/form-data"):
        ten = (request.POST.get("tenSanPham") or "").strip()
        mo_ta = (request.POST.get("moTa") or "").strip()
        gia = request.POST.get("gia") or 0
        danh_muc_id = request.POST.get("danhMucId")

        try:
            gia = int(gia)
        except Exception:
            return JsonResponse({"error": "gia phải là số"}, status=400)

        hinh_anh_urls = []
        if "hinhAnh" in request.FILES:
            file = request.FILES["hinhAnh"]
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "sanpham"))
            filename = fs.save(file.name, file)
            hinh_anh_urls.append("sanpham/" + filename)

        doc = {
            "tenSanPham": ten,
            "moTa": mo_ta,
            "gia": gia,
            "hinhAnh": hinh_anh_urls,
        }

        if danh_muc_id:
            try:
                doc["danhMucId"] = ObjectId(danh_muc_id)
            except Exception:
                return JsonResponse({"error": "Invalid danhMucId"}, status=400)

        res = san_pham.insert_one(doc)
        return JsonResponse({"id": str(res.inserted_id), "tenSanPham": ten, "gia": gia}, status=201)

    # Nếu JSON
    err = _json_required(request)
    if err:
        return err
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ten = (body.get("tenSanPham") or "").strip()
    mo_ta = (body.get("moTa") or "").strip()
    gia = body.get("gia") or 0
    hinh_anh = body.get("hinhAnh") or []
    danh_muc_id = body.get("danhMucId")

    if not ten:
        return JsonResponse({"error": "Thiếu tenSanPham"}, status=400)

    try:
        gia = int(gia)
    except Exception:
        return JsonResponse({"error": "gia phải là số"}, status=400)

    doc = {
        "tenSanPham": ten,
        "moTa": mo_ta,
        "gia": gia,
        "hinhAnh": hinh_anh,
    }

    if danh_muc_id:
        try:
            doc["danhMucId"] = ObjectId(danh_muc_id)
        except Exception:
            return JsonResponse({"error": "Invalid danhMucId"}, status=400)

    res = san_pham.insert_one(doc)
    created = san_pham.find_one({"_id": res.inserted_id})
    if not created:
        return JsonResponse({"error": "Insert failed"}, status=500)

    data = {
        "id": str(created["_id"]),
        "tenSanPham": created.get("tenSanPham", ""),
        "gia": created.get("gia", 0)
    }
    return JsonResponse(data, status=201)


# ================ DETAIL (GET/PUT/DELETE) ==================
@csrf_exempt
def product_detail(request, id):
    """
    GET /api/products/<id>/
    PUT /api/products/<id>/
    DELETE /api/products/<id>/
    """
    try:
        oid = ObjectId(id)
    except Exception:
        return JsonResponse({"error": "Invalid id"}, status=400)

    # ---------- GET ----------
    if request.method == "GET":
        sp = san_pham.find_one({"_id": oid})
        if not sp:
            return JsonResponse({"error": "Not found"}, status=404)

        return JsonResponse({
            "id": str(sp.get("_id")),
            "tenSanPham": sp.get("tenSanPham", ""),
            "moTa": sp.get("moTa", ""),
            "gia": sp.get("gia", 0),
            "hinhAnh": sp.get("hinhAnh", []),
            "danhMucId": str(sp.get("danhMucId")) if sp.get("danhMucId") else None
        })

    # ---------- PUT ----------
    elif request.method == "PUT":
        err = _json_required(request)
        if err: return err
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        update = {}
        if "tenSanPham" in body:
            update["tenSanPham"] = (body.get("tenSanPham") or "").strip()
        if "moTa" in body:
            update["moTa"] = (body.get("moTa") or "").strip()
        if "gia" in body:
            try:
                update["gia"] = int(body.get("gia") or 0)
            except Exception:
                return JsonResponse({"error": "gia phải là số"}, status=400)
        if "hinhAnh" in body:
            update["hinhAnh"] = body.get("hinhAnh") or []
        if "danhMucId" in body:
            try:
                update["danhMucId"] = ObjectId(body["danhMucId"])
            except Exception:
                return JsonResponse({"error": "Invalid danhMucId"}, status=400)

        if not update:
            return JsonResponse({"error": "No fields to update"}, status=400)

        result = san_pham.update_one({"_id": oid}, {"$set": update})
        if result.matched_count == 0:
            return JsonResponse({"error": "Not found"}, status=404)

        sp = san_pham.find_one({"_id": oid})
        if not sp:
            return JsonResponse({"error": "Not found"}, status=404)
        return JsonResponse({
            "id": str(sp.get("_id")),
            "tenSanPham": sp.get("tenSanPham", ""),
            "moTa": sp.get("moTa", ""),
            "gia": sp.get("gia", 0),
            "hinhAnh": sp.get("hinhAnh", []),
            "danhMucId": str(sp.get("danhMucId")) if sp.get("danhMucId") else None
        })

    # ---------- DELETE ----------
    elif request.method == "DELETE":
        deleted = san_pham.delete_one({"_id": oid})
        if deleted.deleted_count == 0:
            return JsonResponse({"error": "Not found"}, status=404)
        return HttpResponse(status=204)

    else:
        return HttpResponseNotAllowed(["GET", "PUT", "DELETE"])

# ============ ADMIN PANEL VIEWS ============

from django.shortcuts import render, redirect
from django.contrib import messages

def product_create(request):
    if request.method == "POST":
        ten = (request.POST.get("tenSanPham") or "").strip()
        mo_ta = (request.POST.get("moTa") or "").strip()
        gia = request.POST.get("gia") or 0
        danh_muc_id = request.POST.get("danhMucId")
        
        try:
            gia = int(gia)
        except:
            messages.error(request, "Giá phải là số!")
            return redirect("shop:admin_product_create")

        doc = {
            "tenSanPham": ten,
            "moTa": mo_ta,
            "gia": gia,
            "hinhAnh": [],
        }
        if danh_muc_id:
            try:
                doc["danhMucId"] = ObjectId(danh_muc_id)
            except:
                messages.error(request, "Mã danh mục không hợp lệ")
                return redirect("shop:admin_product_create")

        san_pham.insert_one(doc)
        messages.success(request, "Thêm sản phẩm thành công!")
        return redirect("shop:admin_products")

    return render(request, "shop/admin/products/products_create.html")


def product_edit(request, id):
    try:
        oid = ObjectId(id)
    except:
        messages.error(request, "ID sản phẩm không hợp lệ")
        return redirect("shop:admin_products")

    sp = san_pham.find_one({"_id": oid})
    if not sp:
        messages.error(request, "Không tìm thấy sản phẩm")
        return redirect("shop:admin_products")

    if request.method == "POST":
        ten = (request.POST.get("tenSanPham") or "").strip()
        mo_ta = (request.POST.get("moTa") or "").strip()
        gia = request.POST.get("gia") or 0
        danh_muc_id = request.POST.get("danhMucId")

        try:
            gia = int(gia)
        except:
            messages.error(request, "Giá phải là số!")
            return redirect("shop:admin_product_edit", id=id)

        update = {
            "tenSanPham": ten,
            "moTa": mo_ta,
            "gia": gia,
        }
        if danh_muc_id:
            try:
                update["danhMucId"] = ObjectId(danh_muc_id)
            except:
                messages.error(request, "Mã danh mục không hợp lệ")
                return redirect("shop:admin_product_edit", id=id)

        san_pham.update_one({"_id": oid}, {"$set": update})
        messages.success(request, "Cập nhật sản phẩm thành công!")
        return redirect("shop:admin_products")

    return render(request, "shop/admin/products/products_edit.html", {"sp": sp})


def product_delete(request, id):
    try:
        oid = ObjectId(id)
    except:
        messages.error(request, "ID sản phẩm không hợp lệ")
        return redirect("shop:admin_products")

    deleted = san_pham.delete_one({"_id": oid})
    if deleted.deleted_count == 0:
        messages.error(request, "Không tìm thấy sản phẩm để xoá")
    else:
        messages.success(request, "Xoá sản phẩm thành công!")

    return redirect("shop:admin_products")

def admin_products_list(request):
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page", 1))

    filter_ = {}
    if q:
        filter_["tenSanPham"] = {"$regex": q, "$options": "i"}

    cursor = san_pham.find(filter_).sort("tenSanPham", 1)
    products = []
    # map danh mục
    cat_map = {str(c["_id"]): c.get("tenDanhMuc", "") for c in danhmuc.find({})}

    for sp in cursor:
        products.append({
            "id": str(sp["_id"]),
            "ten": sp.get("tenSanPham", ""),
            "mo_ta": sp.get("moTa", ""),
            "gia": int(sp.get("gia", 0)),
            "hinh_anh": sp.get("hinhAnh")[0] if sp.get("hinhAnh") else None,
            "danh_muc": cat_map.get(str(sp.get("danhMucId")), "Chưa phân loại"),
        })

    # paginate
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
        "placeholders": range(6 - len(page_obj.object_list)),  # để bảng luôn đủ 6 dòng
    })