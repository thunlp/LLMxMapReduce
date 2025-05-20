from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from backend.app import db
from backend.app.models import User, RedemptionCode, RedemptionRecord
from backend.app.utils.helpers import generate_redemption_code, api_response, jwt_required_custom

redemption_bp = Blueprint('redemption', __name__)

@redemption_bp.route('/generate', methods=['POST'])
@jwt_required_custom
def generate_code():
    """生成兑换码（管理员功能）"""
    data = request.get_json()
    
    # 默认生成1个兑换码，每个兑换码提供1次使用机会
    count = data.get('count', 1) if data else 1
    uses_granted = data.get('uses_granted', 1) if data else 1
    
    codes = []
    for _ in range(count):
        # 生成唯一兑换码
        while True:
            code = generate_redemption_code()
            if not RedemptionCode.query.filter_by(code=code).first():
                break
        
        redemption_code = RedemptionCode(
            code=code,
            uses_granted=uses_granted
        )
        db.session.add(redemption_code)
        codes.append({
            "code": code,
            "uses_granted": uses_granted
        })
    
    db.session.commit()
    
    return api_response(
        data={"codes": codes},
        message=f"成功生成{count}个兑换码"
    )

@redemption_bp.route('/redeem', methods=['POST'])
@jwt_required_custom
def redeem_code():
    """兑换码使用"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return api_response(message="用户不存在", status=404)
    
    data = request.get_json()
    
    if not data or 'code' not in data:
        return api_response(message="请提供兑换码", status=400)
    
    code = data['code']
    
    # 查找兑换码
    redemption_code = RedemptionCode.query.filter_by(code=code, is_used=False).first()
    
    if not redemption_code:
        return api_response(message="兑换码无效或已被使用", status=400)
    
    # 标记兑换码为已使用
    redemption_code.is_used = True
    
    # 增加用户使用次数
    user.remaining_uses += redemption_code.uses_granted
    
    # 记录兑换历史
    record = RedemptionRecord(
        user_id=user.id,
        code=code,
        uses_granted=redemption_code.uses_granted
    )
    
    db.session.add(record)
    db.session.commit()
    
    return api_response(
        data={
            "remaining_uses": user.remaining_uses,
            "added_uses": redemption_code.uses_granted
        },
        message="兑换成功"
    )

@redemption_bp.route('/history', methods=['GET'])
@jwt_required_custom
def get_redemption_history():
    """获取用户兑换历史"""
    user_id = get_jwt_identity()
    
    records = RedemptionRecord.query.filter_by(user_id=user_id).order_by(
        RedemptionRecord.redeemed_at.desc()
    ).all()
    
    history = [{
        "id": record.id,
        "code": record.code,
        "uses_granted": record.uses_granted,
        "redeemed_at": record.redeemed_at.isoformat()
    } for record in records]
    
    return api_response(
        data={"history": history},
        message="获取兑换历史成功"
    )
