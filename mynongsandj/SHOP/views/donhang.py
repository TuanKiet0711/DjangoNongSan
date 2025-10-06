from django.shortcuts import render, redirect

# ==============================
# Trang ĐẶT HÀNG / DANH SÁCH / CHI TIẾT CHO KHÁCH HÀNG
# ==============================

def checkout_page(request):
    if not request.session.get("user_id"):
        return redirect('shop:auth_login_page')
    return render(request, 'customer/checkout.html', {})

def my_orders_page(request):
    if not request.session.get("user_id"):
        return redirect('shop:auth_login_page')
    return render(request, 'customer/indexdonhang.html', {})

def my_order_detail(request, id: str):
    if not request.session.get("user_id"):
        return redirect('shop:auth_login_page')
    return render(request, 'customer/detailsdonhang.html', {"order_id": id})
