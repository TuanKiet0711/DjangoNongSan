# shop/views/home.py
from django.shortcuts import render
from bson import ObjectId
from ..database import sanpham, danhmuc
import random

def home(request):
    """
    Trang chủ hiển thị 8 sản phẩm ngẫu nhiên.
    Ưu tiên dùng $sample của MongoDB; fallback sang random.sample nếu cần.
    """
    try:
        raw_list = list(sanpham.aggregate([{"$sample": {"size": 8}}]))
    except Exception:
        all_items = list(sanpham.find({}, {"tenSanPham": 1, "moTa": 1, "gia": 1, "hinhAnh": 1, "danhMucId": 1}))
        raw_list = random.sample(all_items, min(8, len(all_items)))

    # map danh mục
    cat_ids = [doc.get("danhMucId") for doc in raw_list if isinstance(doc.get("danhMucId"), ObjectId)]
    cat_map = {}
    if cat_ids:
        for c in danhmuc.find({"_id": {"$in": list(set(cat_ids))}}):
            cat_map[str(c["_id"])] = c.get("tenDanhMuc") or "Khác"

    products = []
    for sp in raw_list:
        pid = str(sp.get("_id"))
        cat_id = sp.get("danhMucId")
        if isinstance(cat_id, ObjectId):
            cat_id = str(cat_id)
        imgs = sp.get("hinhAnh") or []
        if not isinstance(imgs, list):
            imgs = [imgs] if imgs else []
        products.append({
            "id": pid,
            "ten": sp.get("tenSanPham") or "Sản phẩm",
            "mo_ta": sp.get("moTa") or "",
            "gia": sp.get("gia", 0),
            "danh_muc_ten": cat_map.get(cat_id, "Khác"),
            "hinh_anh": imgs,
        })

    return render(request, "customer/home.html", {"featured_products": products})
