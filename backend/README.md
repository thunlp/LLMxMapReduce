Flask 后端项目
===========

## 项目结构

```
flask_backend/
├── app/
│   ├── api/
│   │   ├── auth/
│   │   │   └── __init__.py
│   │   ├── redemption/
│   │   │   └── __init__.py
│   │   └── task/
│   │       └── __init__.py
│   ├── utils/
│   │   └── helpers.py
│   ├── __init__.py
│   └── models.py
├── API_DOCUMENTATION.md
├── requirements.txt
├── run.py
└── wsgi.py
```

## 安装与运行

1. 创建虚拟环境（可选但推荐）:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

2. 安装依赖:
```bash
pip install -r requirements.txt
```

3. 运行应用:
```bash
python run.py
```

应用将在 http://localhost:5000 上运行。

## 主要功能

1. **用户系统**
   - 手机号+验证码登录/注册
   - JWT认证
   - 用户信息管理

2. **兑换码系统**
   - 生成兑换码
   - 兑换码验证和使用
   - 兑换历史记录

3. **综述任务管理**
   - 任务创建
   - 任务状态更新
   - 任务列表和详情查询

## API文档

详细的API文档请参阅 [API_DOCUMENTATION.md](API_DOCUMENTATION.md)。

## 数据库

项目使用SQLite作为关系数据库，数据库文件将自动创建在应用实例文件夹中。

## 前端集成

本后端设计用于配合前端应用使用，API设计遵循RESTful风格，主要使用GET和POST请求方法。
