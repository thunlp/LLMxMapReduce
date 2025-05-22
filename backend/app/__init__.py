from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import os
from dotenv import load_dotenv

# 加载.env文件
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

# 初始化数据库
db = SQLAlchemy()
# 初始化JWT
jwt = JWTManager()

def create_app(test_config=None):
    app = Flask(__name__)
    
    # 配置
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key'),
        SQLALCHEMY_DATABASE_URI='sqlite:///app.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret'),
        JWT_ACCESS_TOKEN_EXPIRES=86400  # 1天
    )
    
    # 初始化扩展
    db.init_app(app)
    jwt.init_app(app)
    CORS(app)
    
    # 注册蓝图
    from app.api.auth import auth_bp
    from app.api.redemption import redemption_bp
    from app.api.task import task_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(redemption_bp, url_prefix='/api/redemption')
    app.register_blueprint(task_bp, url_prefix='/api/task')
    
    # 创建数据库表
    with app.app_context():
        db.create_all()
    
    @app.route('/health')
    def health_check():
        return {'status': 'ok'}, 200
    
    return app
