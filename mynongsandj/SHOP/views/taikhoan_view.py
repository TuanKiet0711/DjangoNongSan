# # shop/views/taikhoan_view.py
# from django.http import JsonResponse, HttpResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.views.decorators.http import require_http_methods
# from bson import ObjectId
# from ..database import taikhoan
# import json, re

# PAGE_SIZE_DEFAULT = 10
# PAGE_SIZE_MAX = 100
# EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# def _json_required(request):
#     ctype = request.content_type or ""
#     if not ctype.startswith("application/json"):
#         return JsonResponse({"error": "Content-Type must be application/json"}, status=415)
#     return None

# def _safe_user(doc):
#     if not doc: return None
#     return {
#         "id": str(doc["_id"]),
#         "hoTen": doc.get("hoTen",""),
#         "email": doc.get("email",""),
#         "sdt": doc.get("sdt",""),
#         "vaiTro": doc.get("vaiTro","")
#     }

# # ============ LIST ============
# @require_http_methods(["GET"])
# def accounts_list(request):
#     q = (request.GET.get("q") or "").strip()
#     role = (request.GET.get("vaiTro") or "").strip()
#     try: page = max(int(request.GET.get("page",1)),1)
#     except: page=1
#     try: page_size = min(max(int(request.GET.get("page_size",PAGE_SIZE_DEFAULT)),1),PAGE_SIZE_MAX)
#     except: page_size=PAGE_SIZE_DEFAULT

#     filter_={}
#     ors=[]
#     if q:
#         ors=[{"hoTen":{"$regex":q,"$options":"i"}},
#              {"email":{"$regex":q,"$options":"i"}},
#              {"sdt":{"$regex":q,"$options":"i"}}]
#     if ors: filter_["$or"]=ors
#     if role: filter_["vaiTro"]=role

#     total=taikhoan.count_documents(filter_)
#     skip=(page-1)*page_size
#     cursor=(taikhoan.find(filter_,{"hoTen":1,"email":1,"sdt":1,"vaiTro":1})
#             .sort("hoTen",1).skip(skip).limit(page_size))
#     return JsonResponse({"items":[_safe_user(u) for u in cursor],
#                          "total":total,"page":page,"page_size":page_size})
# # ============ CREATE ============
# @csrf_exempt
# @require_http_methods(["POST"])
# def accounts_create(request):
#     """POST /api/accounts/create"""
#     err=_json_required(request)
#     if err: return err
#     try: body=json.loads(request.body.decode())
#     except: return JsonResponse({"error":"Invalid JSON"},status=400)

#     hoTen=(body.get("hoTen")or"").strip()
#     email=(body.get("email")or"").strip().lower()
#     sdt=(body.get("sdt")or"").strip()
#     matKhau=(body.get("matKhau")or"").strip()
#     vaiTro=(body.get("vaiTro")or"customer").strip() or "customer"
#     if not hoTen or not email or not matKhau:
#         return JsonResponse({"error":"Thiếu hoTen / email / matKhau"},status=400)
#     if not EMAIL_RE.match(email):
#         return JsonResponse({"error":"Email không hợp lệ"},status=400)
#     if taikhoan.find_one({"email":email}):
#         return JsonResponse({"error":"Email đã tồn tại"},status=409)

#     res=taikhoan.insert_one({"hoTen":hoTen,"email":email,"sdt":sdt,
#                              "matKhau":matKhau,"vaiTro":vaiTro})
#     created=taikhoan.find_one({"_id":res.inserted_id})
#     return JsonResponse(_safe_user(created),status=201)

# # ============ EDIT ============
# @csrf_exempt
# @require_http_methods(["PUT"])
# def accounts_edit(request,id):
#     """PUT /api/accounts/<id>/edit"""
#     err=_json_required(request)
#     if err: return err
#     try: oid=ObjectId(id)
#     except: return JsonResponse({"error":"Invalid id"},status=400)
#     try: body=json.loads(request.body.decode())
#     except: return JsonResponse({"error":"Invalid JSON"},status=400)

#     update={}
#     if "hoTen" in body: update["hoTen"]=(body.get("hoTen")or"").strip()
#     if "email" in body:
#         new_email=(body.get("email")or"").strip().lower()
#         if not EMAIL_RE.match(new_email):
#             return JsonResponse({"error":"Email không hợp lệ"},status=400)
#         if taikhoan.find_one({"email":new_email,"_id":{"$ne":oid}}):
#             return JsonResponse({"error":"Email đã tồn tại"},status=409)
#         update["email"]=new_email
#     if "sdt" in body: update["sdt"]=(body.get("sdt")or"").strip()
#     if "vaiTro" in body: update["vaiTro"]=(body.get("vaiTro")or"").strip()
#     if "matKhau" in body and (body.get("matKhau")or"").strip():
#         update["matKhau"]=(body.get("matKhau")or"").strip()
#     if not update:
#         return JsonResponse({"error":"Không có dữ liệu để cập nhật"},status=400)
#     res=taikhoan.update_one({"_id":oid},{"$set":update})
#     if res.matched_count==0:
#         return JsonResponse({"error":"Not found"},status=404)
#     acc=taikhoan.find_one({"_id":oid})
#     return JsonResponse(_safe_user(acc))

# # ============ DELETE ============
# @csrf_exempt
# @require_http_methods(["DELETE"])
# def accounts_delete(request,id):
#     """DELETE /api/accounts/<id>/delete"""
#     try: oid=ObjectId(id)
#     except: return JsonResponse({"error":"Invalid id"},status=400)
#     res=taikhoan.delete_one({"_id":oid})
#     if res.deleted_count==0:
#         return JsonResponse({"error":"Not found"},status=404)
#     return HttpResponse(status=204)

# # ===================== GỘP GET/POST CHO /api/accounts/ =====================

# @csrf_exempt
# def accounts_view(request):
#     if request.method == "GET":
#         return accounts_list(request)
#     elif request.method == "POST":
#         return accounts_create(request)
#     return HttpResponseNotAllowed(["GET", "POST"])

# # ===================== AUTH (không mã hoá mật khẩu) =====================

# @csrf_exempt
# @require_http_methods(["POST"])
# def auth_register(request):
#     """
#     POST /api/auth/register
#     Body: {hoTen, email, sdt?, matKhau}
#     """
#     err = _json_required(request)
#     if err: return err
#     try:
#         body = json.loads(request.body.decode("utf-8"))
#     except Exception:
#         return JsonResponse({"error": "Invalid JSON"}, status=400)

#     hoTen = (body.get("hoTen") or "").strip()
#     email = (body.get("email") or "").strip().lower()
#     sdt   = (body.get("sdt") or "").strip()
#     matKhau = (body.get("matKhau") or "").strip()  # không mã hoá

#     if not hoTen or not email or not matKhau:
#         return JsonResponse({"error": "Thiếu hoTen / email / matKhau"}, status=400)
#     if not EMAIL_RE.match(email):
#         return JsonResponse({"error": "Email không hợp lệ"}, status=400)
#     if taikhoan.find_one({"email": email}):
#         return JsonResponse({"error": "Email đã tồn tại"}, status=409)

#     res = taikhoan.insert_one({
#         "hoTen": hoTen,
#         "email": email,
#         "sdt": sdt,
#         "matKhau": matKhau,   # không mã hoá
#         "vaiTro": "customer"
#     })
#     user = taikhoan.find_one({"_id": res.inserted_id})

#     request.session["user_id"] = str(user["_id"])
#     request.session["user_email"] = user["email"]
#     request.session["user_role"] = user.get("vaiTro", "customer")

#     return JsonResponse({"user": _safe_user(user)}, status=201)

# @csrf_exempt
# @require_http_methods(["POST"])
# def auth_login(request):
#     """
#     POST /api/auth/login
#     Body: {email, matKhau}  (so sánh plain text)
#     """
#     err = _json_required(request)
#     if err: return err
#     try:
#         body = json.loads(request.body.decode("utf-8"))
#     except Exception:
#         return JsonResponse({"error": "Invalid JSON"}, status=400)

#     email = (body.get("email") or "").strip().lower()
#     password = (body.get("matKhau") or "").strip()
#     if not email or not password:
#         return JsonResponse({"error": "Thiếu email / matKhau"}, status=400)

#     user = taikhoan.find_one({"email": email})
#     if not user or password != user.get("matKhau", ""):
#         return JsonResponse({"error": "Email hoặc mật khẩu không đúng"}, status=401)

#     request.session["user_id"] = str(user["_id"])
#     request.session["user_email"] = user["email"]
#     request.session["user_role"] = user.get("vaiTro", "customer")

#     return JsonResponse({"user": _safe_user(user)})

# @csrf_exempt
# @require_http_methods(["POST"])
# def auth_logout(request):
#     request.session.flush()
#     return HttpResponse(status=204)

# @require_http_methods(["GET"])
# def auth_me(request):
#     uid = request.session.get("user_id")
#     if not uid:
#         return JsonResponse({"user": None})
#     try:
#         oid = ObjectId(uid)
#     except Exception:
#         return JsonResponse({"user": None})
#     user = taikhoan.find_one({"_id": oid})
#     return JsonResponse({"user": _safe_user(user) if user else None})

from django.http import HttpResponse
from bson import ObjectId
from ..database import taikhoan
import hashlib

def createsuperadmin(request):
    # Hash mật khẩu
    password = hashlib.md5("123456".encode()).hexdigest()

    admin_data = {
        "_id": ObjectId(),
        "hoTen": "Super Admin",
        "email": "admin@example.com",
        "sdt": "0123456789",
        "matKhau": password,
        "vaiTro": "admin"
    }

    # Nếu đã có admin thì không tạo lại
    if taikhoan.find_one({"email": "admin@example.com"}):
        return HttpResponse("Admin đã tồn tại!")

    taikhoan.insert_one(admin_data)
    return HttpResponse("Tạo admin thành công! Email: admin@example.com, Mật khẩu: 123456")


