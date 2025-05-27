#!/usr/bin/env python3
import unittest
import json
from app import create_app, db
from app.models import User, RedemptionCode, RedemptionRecord

class RedemptionAPITestCase(unittest.TestCase):
    def setUp(self):
        # 创建测试应用
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'JWT_SECRET_KEY': 'test-jwt-secret'
        })
        
        # 创建上下文
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # 创建数据库表
        db.create_all()
        
        # 创建一个测试客户端
        self.client = self.app.test_client()
        
        # 创建一个测试用户并获取token
        self.test_user = User(phone="13800138000")
        db.session.add(self.test_user)
        db.session.commit()
        
        # 创建测试兑换码
        self.test_code = RedemptionCode(
            code="TESTCODE123456",
            uses_granted=5,
            is_used=False
        )
        db.session.add(self.test_code)
        db.session.commit()
        
        # 登录用户获取token
        from flask_jwt_extended import create_access_token
        self.access_token = create_access_token(identity=self.test_user.id)
        
    def tearDown(self):
        # 清理数据库
        db.session.remove()
        db.drop_all()
        
        # 清理上下文
        self.app_context.pop()
    
    def test_generate_code(self):
        """测试生成兑换码功能"""
        response = self.client.post(
            '/api/redemption/generate',
            headers={'Authorization': f'Bearer {self.access_token}'},
            json={'count': 3, 'uses_granted': 2}
        )
        
        # 打印响应内容用于调试
        print(f"生成兑换码响应: {response.data.decode()}")
        
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['data']['codes']), 3)
        
        # 验证数据库中是否创建了3个新的兑换码
        code_count = RedemptionCode.query.count()
        self.assertEqual(code_count, 4)  # 1个初始测试码 + 3个新生成的
    
    def test_redeem_code(self):
        """测试兑换码使用功能"""
        # 获取用户初始使用次数
        initial_uses = self.test_user.remaining_uses
        
        response = self.client.post(
            '/api/redemption/redeem',
            headers={'Authorization': f'Bearer {self.access_token}'},
            json={'code': self.test_code.code}
        )
        
        # 打印响应内容用于调试
        print(f"兑换码使用响应: {response.data.decode()}")
        
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')
        
        # 重新查询用户和兑换码
        db.session.refresh(self.test_user)
        db.session.refresh(self.test_code)
        
        # 验证用户使用次数是否增加
        self.assertEqual(self.test_user.remaining_uses, initial_uses + 5)
        
        # 验证兑换码是否被标记为已使用
        self.assertTrue(self.test_code.is_used)
        
        # 验证是否创建了兑换记录
        record = RedemptionRecord.query.filter_by(user_id=self.test_user.id).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.code, self.test_code.code)
    
    def test_get_redemption_history(self):
        """测试获取兑换历史功能"""
        # 首先使用一个兑换码创建历史记录
        self.client.post(
            '/api/redemption/redeem',
            headers={'Authorization': f'Bearer {self.access_token}'},
            json={'code': self.test_code.code}
        )
        
        # 获取兑换历史
        response = self.client.get(
            '/api/redemption/history',
            headers={'Authorization': f'Bearer {self.access_token}'}
        )
        
        # 打印响应内容用于调试
        print(f"获取兑换历史响应: {response.data.decode()}")
        
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')
        
        # 验证历史记录
        self.assertEqual(len(data['data']['history']), 1)
        self.assertEqual(data['data']['history'][0]['code'], self.test_code.code)
        self.assertEqual(data['data']['history'][0]['uses_granted'], 5)

if __name__ == '__main__':
    unittest.main() 