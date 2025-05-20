from flask import Flask
from flask_cors import CORS
import os

def create_app(test_config=None):
    # 创建并配置应用
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(app.instance_path, 'app.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret'),
        JWT_ACCESS_TOKEN_EXPIRES=86400,  # 1天
    )

    if test_config is None:
        # 加载实例配置（如果存在）
        app.config.from_pyfile('config.py', silent=True)
    else:
        # 加载测试配置
        app.config.from_mapping(test_config)

    # 确保实例文件夹存在
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # 初始化数据库
    from app import db, jwt
    db.init_app(app)
    jwt.init_app(app)
    
    # 启用CORS
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
        from app import db
        from app.models import User, VerificationCode, RedemptionCode, RedemptionRecord, Task
        db.create_all()

    @app.route('/health')
    def health_check():
        return {'status': 'ok'}, 200

    return app
