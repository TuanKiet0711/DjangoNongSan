from django.shortcuts import render, redirect
from django.conf import settings
import stripe
from SHOP.database import donhang
from bson.objectid import ObjectId
from datetime import datetime

stripe.api_key = settings.STRIPE_SECRET_KEY


# ==============================
# TRANG CHECKOUT
# ==============================
def checkout_page(request):
    if not request.session.get("user_id"):
        return redirect('shop:auth_login_page')

    return render(request, 'customer/checkout.html', {
        "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
    })


# ==============================
# TRANG DANH SÁCH ĐƠN HÀNG
# ==============================
def my_orders_page(request):
    if not request.session.get("user_id"):
        return redirect('shop:auth_login_page')
    return render(request, 'customer/indexdonhang.html', {})


# ==============================
# TRANG CHI TIẾT ĐƠN HÀNG (CÓ STRIPE)
# ==============================
def my_order_detail(request, id: str):
    if not request.session.get("user_id"):
        return redirect('shop:auth_login_page')

    # Lấy đơn hàng từ MongoDB
    try:
        order = donhang.find_one({"_id": ObjectId(id)})
    except:
        return render(request, "customer/detailsdonhang.html", {"error": "ID không hợp lệ"})

    if not order:
        return render(request, "customer/detailsdonhang.html", {"error": "Không tìm thấy đơn hàng"})

    paid_success = False

    # Stripe redirect về với session_id
    session_id = request.GET.get("session_id")

    if session_id:
        try:
            # Lấy Checkout Session từ Stripe
            session = stripe.checkout.Session.retrieve(session_id)

            # Lấy payment_intent
            payment_intent_id = session.payment_intent
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Nếu thanh toán OK
            if intent.status == "succeeded":

                # cập nhật MongoDB
                donhang.update_one(
                    {"_id": ObjectId(id)},
                    {
                        "$set": {
                            "trangThai": "da_xac_nhan",
                            "phuongThucThanhToan": "stripe",

                            "stripePayment": {
                                "paymentIntentId": intent.id,
                                "amount": intent.amount,
                                "currency": intent.currency,
                                "payment_method": intent.payment_method,
                                "status": intent.status,
                                "paid_at": datetime.utcnow()
                            },

                            "ngayCapNhat": datetime.utcnow()
                        }
                    }
                )

                paid_success = True
                order = donhang.find_one({"_id": ObjectId(id)})
        except Exception as e:
            print("Stripe ERROR:", e)

    return render(request, "customer/detailsdonhang.html", {
        "order": order,
        "order_id": id,
        "paid_success": paid_success
    })
