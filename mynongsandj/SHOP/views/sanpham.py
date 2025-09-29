from urllib import request
from django.shortcuts import render, redirect
from bson import ObjectId, Regex
from ..database import sanpham, danhmuc, giohang
from django.utils import timezone

def sanpham_list(request):
    # --- Lấy tham số tìm kiếm ---
    q    = (request.GET.get("q") or "").strip()
    cat  = (request.GET.get("cat") or "").strip()
    pmin = request.GET.get("min")  # giá tối thiểu
    pmax = request.GET.get("max")  # giá tối đa

    # --- Lấy danh mục và tạo map id -> tên ---
    categories = list(danhmuc.find({}))
    cat_map = {}
    for catdoc in categories:
        cid = str(catdoc["_id"])
        catdoc["id"] = cid
        cat_map[cid] = catdoc.get("tenDanhMuc") or "Khác"

    # --- Xây query Mongo ---
    mongo_filter = {}

    # lọc danh mục
    if cat:
        try:
            mongo_filter["danhMucId"] = ObjectId(cat)
        except Exception:
            pass  # nếu cat không hợp lệ thì bỏ qua

    # lọc theo khoảng giá
    price_cond = {}
    try:
        if pmin not in (None, ""):
            price_cond["$gte"] = int(pmin)
        if pmax not in (None, ""):
            price_cond["$lte"] = int(pmax)
        if price_cond:
            mongo_filter["gia"] = price_cond
    except ValueError:
        # nếu người dùng nhập không phải số, bỏ lọc giá
        pass

    # Tìm kiếm theo từ khóa trong tên / mô tả (regex, không phân biệt hoa thường)
    if q:
        rx = Regex(q, "i")
        mongo_filter["$or"] = [
            {"tenSanPham": rx},
            {"moTa": rx}
        ]

    # --- Lấy sản phẩm theo filter ---
    cursor = sanpham.find(mongo_filter).sort("_id", -1)  # sort mới nhất trước
    products = list(cursor)

    # --- Chuẩn hoá dữ liệu ra template ---
    for sp in products:
        sp["id"] = str(sp["_id"])
        sp["ten"] = sp.get("tenSanPham") or "Sản phẩm"
        sp["mo_ta"] = sp.get("moTa") or ""
        # Danh mục
        cat_id = sp.get("danhMucId")
        if isinstance(cat_id, ObjectId):
            cat_id = str(cat_id)
        sp["danh_muc_ten"] = cat_map.get(cat_id, "Khác")
        # Ảnh
        imgs = sp.get("hinhAnh") or []
        sp["hinh_anh"] = imgs if isinstance(imgs, list) else [imgs]
        # Giá
        sp["gia"] = sp.get("gia", 0)

    return render(request, "customer/sanpham.html", {
        "categories": categories,
        "products": products,
        # giữ lại giá trị form
        "q": q,
        "cat_selected": cat,
        "min_selected": pmin or "",
        "max_selected": pmax or "",
        "result_count": len(products),
    })


def product_detail(request, sp_id):
    """Trang chi tiết sản phẩm"""
    try:
        oid = ObjectId(sp_id)
    except Exception:
        return render(request, "customer/details.html", {"product": None, "error": "Mã sản phẩm không hợp lệ"})

    sp = sanpham.find_one({"_id": oid})
    if not sp:
        return render(request, "customer/details.html", {"product": None, "error": "Không tìm thấy sản phẩm"})

    # Chuẩn hoá dữ liệu
    prod = {
        "id": str(sp["_id"]),
        "ten": sp.get("tenSanPham") or "Sản phẩm",
        "mo_ta": sp.get("moTa") or "",
        "gia": sp.get("gia", 0),
        "hinh_anh": sp.get("hinhAnh") if isinstance(sp.get("hinhAnh"), list)
                       else ([sp.get("hinhAnh")] if sp.get("hinhAnh") else []),
    }

    # Tên danh mục
    cat_name = "Khác"
    cat_id = sp.get("danhMucId")
    if isinstance(cat_id, ObjectId):
        cat = danhmuc.find_one({"_id": cat_id})
        if cat:
            cat_name = cat.get("tenDanhMuc") or "Khác"
    prod["danh_muc_ten"] = cat_name

    # Sản phẩm liên quan (cùng danh mục, khác id này), tối đa 6
    related = []
    q = {"danhMucId": cat_id} if isinstance(cat_id, ObjectId) else {}
    for rel in sanpham.find(q).limit(12):
        if rel["_id"] == oid:
            continue
        related.append({
            "id": str(rel["_id"]),
            "ten": rel.get("tenSanPham") or "Sản phẩm",
            "gia": rel.get("gia", 0),
            "hinh_anh": (rel.get("hinhAnh") if isinstance(rel.get("hinhAnh"), list)
                        else [rel.get("hinhAnh")] if rel.get("hinhAnh") else []),
        })
        if len(related) >= 6:
            break

    return render(request, "customer/chitietsanpham.html", {"product": prod, "related": related})

def product_by_category(request, cat_id):
    try:
        oid = ObjectId(cat_id)
    except Exception:
        return render(request, "customer/category.html", {"products": [], "error": "Mã danh mục không hợp lệ"})

    products = list(sanpham.find({"danhMucId": oid}))
    for sp in products:
        sp["id"] = str(sp["_id"])
        sp["ten"] = sp.get("tenSanPham") or "Sản phẩm"
        sp["mo_ta"] = sp.get("moTa") or ""
        imgs = sp.get("hinhAnh") or []
        sp["hinh_anh"] = imgs if isinstance(imgs, list) else [imgs]

    return render(request, "customer/category.html", {"products": products})

def add_to_cart(request, sp_id):
    user_str = request.session.get("user_id")
    if not user_str:
        return redirect("shop:shop_login")

    try:
        user_oid = ObjectId(user_str)
        sp_oid = ObjectId(sp_id)
    except Exception:
        return redirect("shop:sanpham_list")

    sp = sanpham.find_one({"_id": sp_oid}, {"gia": 1})
    if not sp:
        return redirect("shop:sanpham_list")

    existing = giohang.find_one({"taiKhoanId": user_oid, "sanPhamId": sp_oid})
    don_gia = int(sp.get("gia", 0))

    if existing:
        so_luong = int(existing.get("soLuong", 0)) + 1
        giohang.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "soLuong": so_luong,
                "donGia": don_gia,
                "tongTien": so_luong * don_gia
            }}
        )
    else:
        giohang.insert_one({
            "taiKhoanId": user_oid,
            "sanPhamId": sp_oid,
            "ngayTao": timezone.now(),
            "soLuong": 1,
            "donGia": don_gia,
            "tongTien": don_gia
        })

    return redirect("shop:sanpham_list")