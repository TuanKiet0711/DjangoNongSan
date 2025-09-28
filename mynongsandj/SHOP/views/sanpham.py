from django.shortcuts import render, redirect
from bson import ObjectId
from ..database import sanpham, danhmuc, giohang
from django.utils import timezone

def sanpham_list(request):
    # Lấy danh mục và tạo map id -> tên
    categories = list(danhmuc.find({}))
    cat_map = {}
    for cat in categories:
        cid = str(cat["_id"])
        cat["id"] = cid
        cat_map[cid] = cat.get("tenDanhMuc") or "Khác"

    # Lấy sản phẩm
    products = list(sanpham.find({}))
    for sp in products:
        sp["id"] = str(sp["_id"])
        sp["ten"] = sp.get("tenSanPham") or "Sản phẩm"
        sp["mo_ta"] = sp.get("moTa") or ""

        # Danh mục
        cat_id = sp.get("danhMucId")
        if isinstance(cat_id, ObjectId):
            cat_id = str(cat_id)
        sp["danh_muc_ten"] = cat_map.get(cat_id, "Khác")

        # Ảnh: đảm bảo có list
        imgs = sp.get("hinhAnh") or []
        sp["hinh_anh"] = imgs if isinstance(imgs, list) else [imgs]

    hot_products = products[:3]
    new_products = products[3:6]

    return render(request, "customer/sanpham.html", {
        "categories": categories,
        "hot_products": hot_products,
        "new_products": new_products,
        "products": products
    })


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
