# SHOP/payment/vnpay.py
from __future__ import annotations

import hashlib
import hmac
from typing import Dict, Iterable, List, Tuple, Any
from urllib.parse import urlencode


# ===================== Helpers =====================

def hmac_sha512(key: str, data: str) -> str:
    """
    Trả về hex digest của HMAC-SHA512(key, data)
    """
    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha512).hexdigest()


def _as_plain_dict(query_params: Any) -> Dict[str, str]:
    """
    Chuyển QueryDict/dict tùy loại về dict {str: str} (không phải list).
    - Với QueryDict: dùng .get(k) -> string
    - Với dict thường: nếu value là list thì lấy phần tử cuối cùng
    """
    # Django QueryDict có .getlist / .keys
    if hasattr(query_params, "getlist") and hasattr(query_params, "keys"):
        return {k: query_params.get(k) for k in query_params.keys()}

    # dict/Mapping bình thường
    if hasattr(query_params, "items"):
        result = {}
        for k, v in query_params.items():
            if isinstance(v, list):
                result[k] = v[-1] if v else ""
            else:
                result[k] = v
        return result

    # Fallback (ít gặp)
    try:
        return dict(query_params)  # type: ignore[arg-type]
    except Exception:
        raise TypeError("query_params must be a QueryDict or dict-like object")


def _sorted_pairs(params: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Lọc & chuẩn hóa tham số:
    - Bỏ None / rỗng ("")
    - Bỏ các trường hash
    - Chuyển value sang str
    - Sắp xếp tăng dần theo key
    """
    filtered: List[Tuple[str, str]] = []
    for k, v in params.items():
        if k in ("vnp_SecureHash", "vnp_SecureHashType"):
            continue
        if v is None or v == "":
            continue
        filtered.append((k, str(v)))
    filtered.sort(key=lambda x: x[0])
    return filtered


# ===================== Build payment URL =====================

def create_payment_url(base_url: str, params: Dict[str, Any], hash_secret: str) -> str:
    """
    Tạo URL thanh toán VNPAY:
    - Ký HMAC SHA512 trên query string đã URL-encode & sắp xếp
    - Gắn thêm tham số vnp_SecureHash vào cuối
    """
    pairs = _sorted_pairs(params)

    # Chuỗi dùng để ký theo spec (URL-encode + giữ nguyên thứ tự đã sort)
    qs_to_sign = urlencode(pairs, doseq=False)
    secure = hmac_sha512(hash_secret, qs_to_sign).upper()

    # Query thực tế gửi đi (cùng thứ tự/encode với qs_to_sign)
    qs = f"{qs_to_sign}&vnp_SecureHash={secure}"
    return f"{base_url}?{qs}"


# ===================== Verify return/IPN =====================

def verify_return(query_params: Any, hash_secret: str) -> bool:
    """
    Xác thực tham số trả về từ VNPAY (Return URL hoặc IPN).
    - Hỗ trợ cả Django QueryDict lẫn dict thường.
    - Loại bỏ vnp_SecureHash và vnp_SecureHashType trước khi tính chữ ký.
    - So sánh chữ ký theo kiểu không phân biệt hoa/thường.
    """
    # Đưa về dict string->string để tránh lỗi list
    data = _as_plain_dict(query_params)

    # Lấy hash do VNPAY gửi rồi bỏ khỏi data trước khi ký
    given = (data.pop("vnp_SecureHash", "") or "")
    data.pop("vnp_SecureHashType", None)

    # Build chuỗi ký theo đúng quy tắc tạo URL
    pairs = _sorted_pairs(data)
    qs_to_sign = urlencode(pairs, doseq=False)

    calc = hmac_sha512(hash_secret, qs_to_sign)

    # VNPAY thường trả UPPERCASE; so sánh không phân biệt hoa/thường
    return calc.upper() == given.upper()
