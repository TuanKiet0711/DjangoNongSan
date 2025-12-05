import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Stripe Secret Key
stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_exempt
def create_checkout_session(request):
    """
    Tạo Stripe Checkout Session để thanh toán đơn hàng.
    Không cần nhập thẻ trên web, Stripe tự xử lý.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        # Nhận amount và order_id từ frontend
        amount = int(request.POST.get("amount"))
        order_id = request.POST.get("order_id")

        if not amount or not order_id:
            return JsonResponse({"error": "Missing amount or order_id"}, status=400)

        # Tạo session thanh toán
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],

            line_items=[{
                "price_data": {
                    "currency": "vnd",
                    "product_data": {
                        "name": f"Thanh toán đơn hàng #{order_id}"
                    },
                    "unit_amount": amount,  # Ví dụ: 45000 = 45.000đ
                },
                "quantity": 1,
            }],

            mode="payment",

            metadata={"order_id": order_id},

          success_url=f"{settings.DOMAIN}/don-hang/{order_id}/?session_id={{CHECKOUT_SESSION_ID}}",

            cancel_url=f"{settings.DOMAIN}/don-hang/{order_id}/?paid=0",
        )

        return JsonResponse({"url": session.url})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
