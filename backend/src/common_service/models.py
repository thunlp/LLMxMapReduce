from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json

# 创建Flask-SQLAlchemy实例
db = SQLAlchemy()

class User(db.Model):
    """用户表"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    phone = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # 用户剩余使用次数
    remaining_uses = Column(Integer, default=0)
    
    # 关联
    tasks = relationship("Task", back_populates="user")
    redemption_records = relationship("RedemptionRecord", back_populates="user")
    
    def __repr__(self):
        return f'<User {self.phone}>'


class VerificationCode(db.Model):
    """验证码表"""
    __tablename__ = 'verification_codes'
    
    id = Column(Integer, primary_key=True)
    phone = Column(String(20), nullable=False)
    code = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    
    def __repr__(self):
        return f'<VerificationCode {self.phone}:{self.code}>'


class RedemptionCode(db.Model):
    """兑换码表"""
    __tablename__ = 'redemption_codes'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, nullable=False)
    uses_granted = Column(Integer, default=1)  # 兑换后获得的使用次数
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<RedemptionCode {self.code}>'


class RedemptionRecord(db.Model):
    """兑换记录表"""
    __tablename__ = 'redemption_records'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    code = Column(String(16), nullable=False)
    uses_granted = Column(Integer, nullable=False)
    redeemed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 关联
    user = relationship("User", back_populates="redemption_records")
    
    def __repr__(self):
        return f'<RedemptionRecord {self.user_id}:{self.code}>'
    

class Task(db.Model):
    """任务表"""
    __tablename__ = 'tasks'
    
    # 数据库主键
    id = Column(Integer, primary_key=True)
    
    # 业务层面的任务ID（UUID格式，用于外部API）
    task_id = Column(String(36), unique=True, nullable=False, index=True)
    
    # 关联用户
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # 任务状态
    status = Column(String(20), nullable=False, index=True)
    
    # 任务参数（JSON格式存储）
    params = Column(Text)
    
    # 时间字段
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    
    # 执行时间（秒）
    execution_seconds = Column(Float)
    
    # 错误信息
    error = Column(Text)
    
    # 过期时间
    expire_at = Column(DateTime, nullable=False, index=True)
    
    # 任务结果数据（JSON格式存储）
    result_data = Column(Text)
    
    # 重试次数
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # 关联
    user = relationship("User", back_populates="tasks")
    
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
        current_time = datetime.now(timezone.utc)
        
        # 确保expire_at有时区信息
        if self.expire_at.tzinfo is None:
            # 如果expire_at没有时区信息，假设它是UTC时间
            expire_at_utc = self.expire_at.replace(tzinfo=timezone.utc)
        else:
            expire_at_utc = self.expire_at
        
        return current_time > expire_at_utc
    
    def can_retry(self):
        """检查是否可以重试"""
        return self.retry_count < self.max_retries