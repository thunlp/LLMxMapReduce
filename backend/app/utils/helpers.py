import random
import string
from datetime import datetime, timedelta
from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

def generate_verification_code(length=6):
    """生成数字验证码"""
    return ''.join(random.choices(string.digits, k=length))

def generate_redemption_code(length=16):
    """生成兑换码"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

def api_response(data=None, message="", status=200):
    """统一API响应格式"""
    response = {
        "status": "success" if status < 400 else "error",
        "message": message,
    }
    
    if data is not None:
        response["data"] = data
        
    return jsonify(response), status

def jwt_required_custom(fn):
    """自定义JWT验证装饰器"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            return fn(*args, **kwargs)
        except Exception as e:
            return api_response(message="认证失败，请重新登录", status=401)
    return wrapper
