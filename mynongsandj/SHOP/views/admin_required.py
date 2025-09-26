from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        role = (request.session.get("user_role") or "").lower()
        if role == "admin":
            return view_func(request, *args, **kwargs)
        messages.error(request, "Bạn không có quyền truy cập trang quản trị.")
        return redirect("shop:home")
    return _wrapped
