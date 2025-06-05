from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone
from flask_jwt_extended import create_access_token, get_jwt_identity
from src.common_service.models import db, User, VerificationCode
from src.common_service.helpers import generate_verification_code, api_response, jwt_required_custom
from src.common_service.auth.tencent_sms import get_sms_client
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/send_code', methods=['POST'])
def send_verification_code():
    """发送短信验证码"""
    data = request.get_json()

    if not data or 'phone' not in data:
        return api_response(message="请提供手机号", status=400)

    phone = data['phone']

    # 生成6位数字验证码
    code = generate_verification_code()

    # 设置过期时间（10分钟）
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    # 存储验证码
    verification = VerificationCode(
        phone=phone,
        code=code,
        expires_at=expires_at
    )

    # 如果已存在未过期的验证码，则更新它
    existing_code = VerificationCode.query.filter_by(
        phone=phone,
        is_used=False
    ).filter(
        VerificationCode.expires_at > datetime.now(timezone.utc)
    ).first()

    if existing_code:
        existing_code.code = code
        existing_code.expires_at = expires_at
    else:
        db.session.add(verification)

    db.session.commit()

    # 调用腾讯云短信服务发送验证码
    try:
        # 判断是否为开发环境
        if os.environ.get("FLASK_ENV") == "dev":
            # 开发环境下不发送真实短信，直接返回验证码
            logger.info(f"开发环境模式，生成的验证码: {code}")
            return api_response(
                data={"code": code},  # 开发环境返回验证码用于测试
                message="验证码已生成（开发模式）"
            )
        else:
            # 生产环境发送短信验证码，有效期10分钟
            sms_client = get_sms_client()
            result = sms_client.send_verification_code(
                phone_number=phone,
                code=code,
                minutes=10
            )
            
            logger.info(f"短信发送结果: {result}")

            if result.get("success"):
                return api_response(message="验证码已发送")
            else:
                # 短信发送失败
                logger.error(f"短信发送失败: {result.get('message')}")
                return api_response(message="验证码发送失败，请稍后重试", status=500)

    except Exception as e:
        logger.exception("发送短信时发生异常")
        return api_response(message="验证码发送失败，请稍后重试", status=500)


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录（同时处理注册）"""
    data = request.get_json()

    if not data or 'phone' not in data or 'code' not in data:
        return api_response(message="请提供手机号和验证码", status=400)

    phone = data['phone']
    code = data['code']

    # 验证验证码
    verification = VerificationCode.query.filter_by(
        phone=phone,
        code=code,
        is_used=False
    ).filter(
        VerificationCode.expires_at > datetime.now(timezone.utc)
    ).first()

    if not verification:
        return api_response(message="验证码无效或已过期", status=400)

    # 标记验证码为已使用
    verification.is_used = True
    db.session.commit()

    # 查找用户，如不存在则创建（注册）
    user = User.query.filter_by(phone=phone).first()

    if not user:
        user = User(phone=phone)
        db.session.add(user)
        db.session.commit()

    # 生成JWT令牌
    access_token = create_access_token(identity=user.id)

    return api_response(
        data={
            "token": access_token,
            "user": {
                "id": user.id,
                "phone": user.phone,
                "remaining_uses": user.remaining_uses
            }
        },
        message="登录成功"
    )


@auth_bp.route('/user_info', methods=['GET'])
@jwt_required_custom
def get_user_info():
    """获取用户信息"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return api_response(message="用户不存在", status=404)

    return api_response(
        data={
            "id": user.id,
            "phone": user.phone,
            "remaining_uses": user.remaining_uses,
            "created_at": user.created_at.isoformat()
        },
        message="获取用户信息成功"
    )