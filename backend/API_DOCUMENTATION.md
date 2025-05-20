Flask 后端 API 文档
==============

本文档详细介绍了为前端应用开发的 Flask 后端 API。

## 基本信息

- 基础URL: `http://localhost:5000`
- 认证方式: JWT Token
- 数据格式: JSON

## 认证机制

除了登录和发送验证码接口外，所有 API 都需要在请求头中包含 JWT 令牌:

```
Authorization: Bearer <token>
```

## 1. 用户认证 API

### 1.1 发送验证码

- **URL**: `/api/auth/send_code`
- **方法**: `POST`
- **认证**: 不需要
- **请求体**:
  ```json
  {
    "phone": "13800138000"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "验证码已发送",
    "data": {
      "code": "123456"  // 仅测试环境返回，生产环境不会返回
    }
  }
  ```
- **错误响应** (400):
  ```json
  {
    "status": "error",
    "message": "请提供手机号"
  }
  ```

### 1.2 用户登录/注册

- **URL**: `/api/auth/login`
- **方法**: `POST`
- **认证**: 不需要
- **请求体**:
  ```json
  {
    "phone": "13800138000",
    "code": "123456"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "登录成功",
    "data": {
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "user": {
        "id": 1,
        "phone": "13800138000",
        "remaining_uses": 0
      }
    }
  }
  ```
- **错误响应** (400):
  ```json
  {
    "status": "error",
    "message": "验证码无效或已过期"
  }
  ```

### 1.3 获取用户信息

- **URL**: `/api/auth/user_info`
- **方法**: `GET`
- **认证**: 需要
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "获取用户信息成功",
    "data": {
      "id": 1,
      "phone": "13800138000",
      "remaining_uses": 5,
      "created_at": "2025-05-20T04:30:00.000000"
    }
  }
  ```
- **错误响应** (401):
  ```json
  {
    "status": "error",
    "message": "认证失败，请重新登录"
  }
  ```

## 2. 兑换码 API

### 2.1 生成兑换码

- **URL**: `/api/redemption/generate`
- **方法**: `POST`
- **认证**: 需要
- **请求体**:
  ```json
  {
    "count": 5,
    "uses_granted": 1
  }
  ```
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "成功生成5个兑换码",
    "data": {
      "codes": [
        {
          "code": "ABC123DEF456GHI7",
          "uses_granted": 1
        },
        // ...更多兑换码
      ]
    }
  }
  ```

### 2.2 使用兑换码

- **URL**: `/api/redemption/redeem`
- **方法**: `POST`
- **认证**: 需要
- **请求体**:
  ```json
  {
    "code": "ABC123DEF456GHI7"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "兑换成功",
    "data": {
      "remaining_uses": 6,
      "added_uses": 1
    }
  }
  ```
- **错误响应** (400):
  ```json
  {
    "status": "error",
    "message": "兑换码无效或已被使用"
  }
  ```

### 2.3 获取兑换历史

- **URL**: `/api/redemption/history`
- **方法**: `GET`
- **认证**: 需要
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "获取兑换历史成功",
    "data": {
      "history": [
        {
          "id": 1,
          "code": "ABC123DEF456GHI7",
          "uses_granted": 1,
          "redeemed_at": "2025-05-20T04:45:00.000000"
        },
        // ...更多兑换记录
      ]
    }
  }
  ```

## 3. 任务管理 API

### 3.1 创建任务

- **URL**: `/api/task/create`
- **方法**: `POST`
- **认证**: 需要
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "任务创建成功",
    "data": {
      "task_id": 1
    }
  }
  ```
- **错误响应** (403):
  ```json
  {
    "status": "error",
    "message": "使用次数不足，请兑换后再试"
  }
  ```

### 3.2 更新任务状态

- **URL**: `/api/task/update_status`
- **方法**: `POST`
- **认证**: 需要
- **请求体**:
  ```json
  {
    "task_id": 1,
    "status": "处理中",
    "error": "可选错误信息",
    "output_file_path": "可选输出文件路径"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "任务状态更新成功",
    "data": {
      "task_id": 1,
      "status": "处理中"
    }
  }
  ```
- **错误响应** (400):
  ```json
  {
    "status": "error",
    "message": "无效的任务状态"
  }
  ```

### 3.3 获取任务列表

- **URL**: `/api/task/list`
- **方法**: `GET`
- **认证**: 需要
- **查询参数**:
  - `page`: 页码，默认为1
  - `per_page`: 每页数量，默认为10
  - `status`: 可选，按状态筛选
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "获取任务列表成功",
    "data": {
      "tasks": [
        {
          "id": 1,
          "status": "完成",
          "start_time": "2025-05-20T04:50:00.000000",
          "end_time": "2025-05-20T04:55:00.000000",
          "execution_time": 300.0,
          "created_at": "2025-05-20T04:49:00.000000",
          "output_file_path": "/path/to/output.pdf"
        },
        // ...更多任务
      ],
      "pagination": {
        "total": 15,
        "pages": 2,
        "current_page": 1,
        "per_page": 10
      }
    }
  }
  ```

### 3.4 获取任务详情

- **URL**: `/api/task/detail/<task_id>`
- **方法**: `GET`
- **认证**: 需要
- **成功响应** (200):
  ```json
  {
    "status": "success",
    "message": "获取任务详情成功",
    "data": {
      "task": {
        "id": 1,
        "status": "完成",
        "start_time": "2025-05-20T04:50:00.000000",
        "end_time": "2025-05-20T04:55:00.000000",
        "execution_time": 300.0,
        "error": null,
        "output_file_path": "/path/to/output.pdf",
        "created_at": "2025-05-20T04:49:00.000000",
        "updated_at": "2025-05-20T04:55:00.000000"
      }
    }
  }
  ```
- **错误响应** (404):
  ```json
  {
    "status": "error",
    "message": "任务不存在或无权访问"
  }
  ```

## 4. 健康检查 API

### 4.1 健康检查

- **URL**: `/health`
- **方法**: `GET`
- **认证**: 不需要
- **成功响应** (200):
  ```json
  {
    "status": "ok"
  }
  ```
