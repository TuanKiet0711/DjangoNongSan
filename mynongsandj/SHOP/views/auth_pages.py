# SHOP/views/auth_pages.py
from django.shortcuts import render, redirect

def login_page(request):
    # Nếu đã đăng nhập thì đi thẳng
    role = (request.session.get("user_role") or "").lower()
    if role == "admin":
        return redirect("/admin-panel/")
    if role:
        return redirect("/")
    return render(request, "shop/auth/login.html")

def register_page(request):
    role = (request.session.get("user_role") or "").lower()
    if role == "admin":
        return redirect("/admin-panel/")
    if role:
        return redirect("/")
    return render(request, "shop/auth/register.html")

def logout_view(request):
    # Cho nhanh: xoá session phía server (tương đương gọi API /api/auth/logout)
    request.session.flush()
    return redirect("/")
