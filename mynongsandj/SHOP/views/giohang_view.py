# from django.http import JsonResponse
# from bson import ObjectId
# from django.utils import timezone
# from ..database import sanpham, giohang

# def api_add_to_cart(request, sp_id):
#     if not request.session.get("user_id"):
#         return JsonResponse({"error": "not_authenticated"}, status=401)

#     try:
#         user_oid = ObjectId(request.session["user_id"])
#         sp_oid = ObjectId(sp_id)
#     except Exception:
#         return JsonResponse({"error": "invalid_id"}, status=400)

#     sp = sanpham.find_one({"_id": sp_oid}, {"gia": 1})
#     if not sp:
#         return JsonResponse({"error": "product_not_found"}, status=404)

#     don_gia = int(sp.get("gia", 0))
#     existing = giohang.find_one({"tai_khoan_id": user_oid, "san_pham_id": sp_oid})

#     if existing:
#         so_luong = int(existing.get("so_luong", 0)) + 1
#         giohang.update_one(
#             {"_id": existing["_id"]},
#             {"$set": {
#                 "so_luong": so_luong,
#                 "don_gia": don_gia,
#                 "tong_tien": so_luong * don_gia,
#                 "ngay_tao": timezone.now()
#             }}
#         )
#     else:
#         giohang.insert_one({
#             "tai_khoan_id": user_oid,
#             "san_pham_id": sp_oid,
#             "ngay_tao": timezone.now(),
#             "so_luong": 1,
#             "don_gia": don_gia,
#             "tong_tien": don_gia
#         })

#     return JsonResponse({"success": True, "message": "added_to_cart"})
