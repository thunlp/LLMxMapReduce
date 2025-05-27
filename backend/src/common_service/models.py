from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json

db = SQLAlchemy()

class User(db.Model):
    """用户表"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # 用户剩余使用次数
    remaining_uses = db.Column(db.Integer, default=0)
    
    # 关联
    tasks = db.relationship('Task', backref='user', lazy=True)
    redemption_records = db.relationship('RedemptionRecord', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.phone}>'


class VerificationCode(db.Model):
    """验证码表"""
    __tablename__ = 'verification_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<VerificationCode {self.phone}:{self.code}>'


class RedemptionCode(db.Model):
    """兑换码表"""
    __tablename__ = 'redemption_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    uses_granted = db.Column(db.Integer, default=1)  # 兑换后获得的使用次数
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<RedemptionCode {self.code}>'


class RedemptionRecord(db.Model):
    """兑换记录表"""
    __tablename__ = 'redemption_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    code = db.Column(db.String(16), nullable=False)
    uses_granted = db.Column(db.Integer, nullable=False)
    redeemed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<RedemptionRecord {self.user_id}:{self.code}>'
    

class Task(db.Model):
    """任务表 - 增强版本，支持完整的任务管理功能"""
    __tablename__ = 'tasks'
    
    # 数据库主键
    id = db.Column(db.Integer, primary_key=True)
    
    # 业务层面的任务ID（UUID格式，用于外部API）
    task_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    
    # 关联用户
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 任务状态
    status = db.Column(db.String(20), nullable=False, index=True)
    
    # 任务参数（JSON格式存储）
    params = db.Column(db.Text)
    
    # 时间字段
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    
    # 执行时间（秒）
    execution_seconds = db.Column(db.Float)
    
    # 错误信息
    error = db.Column(db.Text)
    
    # 过期时间
    expire_at = db.Column(db.DateTime, nullable=False, index=True)
    
    # 任务结果数据（JSON格式存储）
    result_data = db.Column(db.Text)
    
    # 任务优先级
    priority = db.Column(db.Integer, default=0)
    
    # 重试次数
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    def __repr__(self):
        return f'<Task {self.task_id}:{self.status}>'
    
    def to_dict(self):
        """转换为字典格式，便于API返回"""
        data = {
            'id': self.task_id,  # 对外使用task_id
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'execution_seconds': self.execution_seconds,
            'error': self.error,
            'expire_at': self.expire_at.isoformat() if self.expire_at else None,
            'priority': self.priority,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }
        
        # 解析JSON字段
        if self.params:
            try:
                data['params'] = json.loads(self.params)
            except json.JSONDecodeError:
                data['params'] = {}
        
        if self.result_data:
            try:
                data['result_data'] = json.loads(self.result_data)
            except json.JSONDecodeError:
                data['result_data'] = {}
        
        # 计算执行时间字符串
        if self.start_time and self.end_time:
            execution_time = self.end_time - self.start_time
            data['execution_time'] = str(execution_time)
        
        return data
    
    def set_params(self, params_dict):
        """设置任务参数"""
        if params_dict:
            self.params = json.dumps(params_dict, ensure_ascii=False)
    
    def get_params(self):
        """获取任务参数"""
        if self.params:
            try:
                return json.loads(self.params)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_result_data(self, result_dict):
        """设置任务结果"""
        if result_dict:
            self.result_data = json.dumps(result_dict, ensure_ascii=False)
    
    def get_result_data(self):
        """获取任务结果"""
        if self.result_data:
            try:
                return json.loads(self.result_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def is_expired(self):
        """检查任务是否过期"""
        return datetime.now(timezone.utc) > self.expire_at
    
    def can_retry(self):
        """检查是否可以重试"""
        return self.retry_count < self.max_retries