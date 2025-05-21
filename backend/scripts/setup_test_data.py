#!/usr/bin/env python3
from app import create_app, db
from app.models import User, RedemptionCode
from flask_jwt_extended import create_access_token
import json

def setup_test_data():
    """创建测试用户和兑换码数据"""
    app = create_app()
    with app.app_context():
        # 创建测试用户
        test_user = User.query.filter_by(phone="13800138000").first()
        if not test_user:
            test_user = User(
                phone="13800138000",
                remaining_uses=0  # 初始设为0次使用机会
            )
            db.session.add(test_user)
            db.session.commit()
            print(f"创建测试用户成功: id={test_user.id}, phone={test_user.phone}")
        else:
            print(f"测试用户已存在: id={test_user.id}, phone={test_user.phone}")
        
        # 为测试用户生成JWT令牌
        access_token = create_access_token(identity=test_user.id)
        print(f"\n测试用户的JWT令牌:\n{access_token}\n")
        
        # 创建测试兑换码
        test_code = RedemptionCode.query.filter_by(code="TEST1234567890").first()
        if not test_code:
            test_code = RedemptionCode(
                code="TEST1234567890",
                uses_granted=10,
                is_used=False
            )
            db.session.add(test_code)
            db.session.commit()
            print(f"创建测试兑换码成功: code={test_code.code}, uses_granted={test_code.uses_granted}")
        else:
            print(f"测试兑换码已存在: code={test_code.code}, uses_granted={test_code.uses_granted}")
        
        # 打印测试API的curl命令
        print("\n测试API的curl命令:")
        print(f"1. 兑换码使用: curl -X POST http://localhost:5001/api/redemption/redeem -H \"Authorization: Bearer {access_token}\" -H \"Content-Type: application/json\" -d '{{\"code\": \"{test_code.code}\"}}'")
        print(f"2. 获取兑换历史: curl -X GET http://localhost:5001/api/redemption/history -H \"Authorization: Bearer {access_token}\"")
        print(f"3. 生成新兑换码: curl -X POST http://localhost:5001/api/redemption/generate -H \"Authorization: Bearer {access_token}\" -H \"Content-Type: application/json\" -d '{{\"count\": 2, \"uses_granted\": 5}}'")
        
        # 创建一个测试配置文件，用于postman等工具测试
        test_config = {
            "baseUrl": "http://localhost:5001",
            "authToken": access_token,
            "testUser": {
                "id": test_user.id,
                "phone": test_user.phone
            },
            "testRedemptionCode": test_code.code
        }
        
        with open("test_config.json", "w") as f:
            json.dump(test_config, f, indent=2)
        print("\n测试配置已保存到test_config.json文件中")

if __name__ == "__main__":
    setup_test_data() 