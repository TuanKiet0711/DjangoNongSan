# SHOP/views/payment_vnpay.py
from datetime import datetime, timedelta

from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from ..database import donhang
from .donhang_view import require_login_api, _int, _oid
from ..payment.vnpay import create_payment_url, verify_return


def _own(user_oid, order) -> bool:
    return bool(order) and order.get("taiKhoanId") == user_oid


# ===================== CREATE PAYMENT URL =====================
@require_http_methods(["GET"])
@require_login_api
def vnpay_create(request, id):
    """
    Sinh URL thanh toán VNPAY cho đơn đã được /api/orders/checkout tạo sẵn.
    """
    oid = _oid(id)
    if not oid:
        return JsonResponse({"error": "invalid_id"}, status=400)

    order = donhang.find_one({"_id": oid})
    if not _own(request.user_oid, order):
        return JsonResponse({"error": "forbidden_or_notfound"}, status=404)

    amount = _int(order.get("tongTien", 0))
    if amount <= 0:
        return JsonResponse({"error": "invalid_amount"}, status=400)

    # VNPAY yêu cầu IP, TxnRef (chỉ chữ/số), Create/ExpireDate định dạng YYYYMMDDHHMMSS
    ip = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "127.0.0.1"
    txn_ref = str(order["_id"])
    now = datetime.now()
    expire = now + timedelta(minutes=15)

    params = {
        "vnp_Version":    settings.VNPAY_VERSION,
        "vnp_Command":    settings.VNPAY_COMMAND,
        "vnp_TmnCode":    settings.VNPAY_TMN_CODE,
        "vnp_Amount":     amount * 100,  # VND * 100 (số nguyên)
        "vnp_CurrCode":   settings.VNPAY_CURRENCY,
        "vnp_TxnRef":     txn_ref,
        "vnp_OrderInfo":  f"Thanh toan don hang {txn_ref}",
        "vnp_OrderType":  "other",
        "vnp_Locale":     settings.VNPAY_LOCALE,         # 'vn' hoặc 'en'
        "vnp_ReturnUrl":  settings.VNPAY_RETURN_URL,     # HTTPS public
        "vnp_IpAddr":     ip,
        "vnp_CreateDate": now.strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": expire.strftime("%Y%m%d%H%M%S"),
        # "vnp_BankCode": settings.VNPAY_BANK_CODE or "",
    }

    pay_url = create_payment_url(settings.VNPAY_PAYMENT_URL, params, settings.VNPAY_HASH_SECRET)

    # Ghi nhận khách chọn VNPAY (chưa đổi trạng thái ở đây)
    donhang.update_one({"_id": oid}, {"$set": {
        "phuongThucThanhToan": "vnpay",
        "ngayCapNhat": timezone.now(),
    }})

    return HttpResponseRedirect(pay_url)


# ===================== RETURN URL (BROWSER) =====================
@require_http_methods(["GET"])
def vnpay_return(request):
    """
    VNPAY redirect người dùng về.
    Thành công (vnp_ResponseCode == '00') -> cập nhật 'da_xac_nhan' và chuyển tới /don-hang/<id>/?paid=1
    """
    qs = request.GET
    if not verify_return(qs, settings.VNPAY_HASH_SECRET):
        return HttpResponse("Invalid signature", status=400)

    rsp_code = qs.get("vnp_ResponseCode")
    order_id = _oid(qs.get("vnp_TxnRef"))
    if not order_id:
        return HttpResponse("Invalid order", status=400)

    if rsp_code == "00":
        donhang.update_one({"_id": order_id}, {"$set": {
            "trangThai": "da_xac_nhan",
            "ngayCapNhat": timezone.now(),
            "vnpay": {
                "transactionNo": qs.get("vnp_TransactionNo"),
                "bankCode": qs.get("vnp_BankCode"),
                "cardType": qs.get("vnp_CardType"),
                "payDate": qs.get("vnp_PayDate"),
                "amount": int(qs.get("vnp_Amount", "0") or 0),
                "responseCode": rsp_code,
            }
        }})
        url = reverse("shop:customer_order_detail", kwargs={"id": str(order_id)})
        return HttpResponseRedirect(f"{url}?paid=1")

    # thất bại: giữ 'cho_xu_ly'
    donhang.update_one({"_id": order_id}, {"$set": {
        "trangThai": "cho_xu_ly",
        "ngayCapNhat": timezone.now(),
        "vnpay": {"responseCode": rsp_code}
    }})
    url = reverse("shop:customer_order_detail", kwargs={"id": str(order_id)})
    return HttpResponseRedirect(f"{url}?pay=failed")


# ===================== IPN (SERVER-TO-SERVER) =====================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def vnpay_ipn(request):
    """
    (Tùy chọn) IPN từ VNPAY để xác thực lại kết quả.
    Trả JSON theo Spec VNPAY: RspCode/Message.
    """
    data = request.GET or request.POST
    if not verify_return(data, settings.VNPAY_HASH_SECRET):
        return JsonResponse({"RspCode": "97", "Message": "Invalid signature"})

    rsp = data.get("vnp_ResponseCode")
    order_id = _oid(data.get("vnp_TxnRef"))
    if not order_id:
        return JsonResponse({"RspCode": "01", "Message": "Order not found"})

    if rsp == "00":
        donhang.update_one({"_id": order_id}, {"$set": {
            "trangThai": "da_xac_nhan",
            "ngayCapNhat": timezone.now(),
            "vnpay_ipn": dict(data),
        }})
        return JsonResponse({"RspCode": "00", "Message": "Confirm Success"})
    return JsonResponse({"RspCode": "00", "Message": "Confirm Fail"})
