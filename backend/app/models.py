from backend.app import db
from datetime import datetime, timezone

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
    """任务表"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 任务状态: "准备", "处理中", "完成"
    status = db.Column(db.String(20), nullable=False, default="准备")
    
    # 时间记录
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    execution_time = db.Column(db.Float)  # 执行时间（秒）
    
    # 错误信息
    error = db.Column(db.Text)
    
    # 输出文件路径
    output_file_path = db.Column(db.String(255))
    
    # 任务创建和更新时间
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Task {self.id}:{self.status}>'
