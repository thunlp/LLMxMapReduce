# Task Management API Documentation

## 概述
任务管理系统API提供RESTful接口，支持用户认证、任务管理、兑换码系统等功能。

**Base URL**: `https://api.example.com/api/v1`

**认证方式**: JWT Bearer Token

## 认证接口 (Authentication)

### 1. 发送短信验证码
```http
POST /auth/send_code
```

发送短信验证码到指定手机号。

**请求参数**:
```json
{
  "phone": "string" // 手机号码，必填
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "验证码已发送",
  "data": null
}
```

**开发环境响应**:
```json
{
  "success": true,
  "message": "验证码发送失败，但已生成用于测试",
  "data": {
    "code": "123456"
  }
}
```

**错误响应**:
- `400 Bad Request`: 缺少手机号参数
- `500 Internal Server Error`: 短信发送失败

---

### 2. 用户登录/注册
```http
POST /auth/login
```

使用手机号和验证码进行登录，不存在的用户将自动注册。

**请求参数**:
```json
{
  "phone": "string",    // 手机号码，必填
  "code": "string"      // 验证码，必填
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": 1,
      "phone": "13800138000",
      "remaining_uses": 5
    }
  }
}
```

**错误响应**:
- `400 Bad Request`: 缺少必需参数或验证码无效

---

### 3. 获取用户信息
```http
GET /auth/user_info
```

获取当前登录用户的详细信息。

**请求头**:
```
Authorization: Bearer <token>
```

**响应示例**:
```json
{
  "success": true,
  "message": "获取用户信息成功",
  "data": {
    "id": 1,
    "phone": "13800138000",
    "remaining_uses": 5,
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

**错误响应**:
- `401 Unauthorized`: 未提供有效token
- `404 Not Found`: 用户不存在

---

## 任务管理接口 (Task Management)

### 4. 提交任务
```http
POST /task/submit
```

提交新的研究任务到Pipeline处理队列。

**请求头**:
```
Authorization: Bearer <token>
Content-Type: application/json
```

**请求参数**:
```json
{
  "topic": "string",           // 研究主题，与input_file互斥
  "description": "string",     // 主题描述，可选
  "output_file": "string",     // 输出文件路径，可选
  "config_file": "string",     // 配置文件路径，可选
  "search_model": "string",    // 搜索模型，可选
  "block_count": 10,           // 块数量，可选
  "data_num": 100,             // 数据数量，可选
  "top_n": 20,                 // 返回结果数量，可选
  "input_file": "string"       // 输入文件路径，与topic互斥，可选
}
```

**响应示例**:
```json
{
  "success": true,
  "task_id": "task_12345",
  "message": "任务已提交",
  "output_file": "/path/to/output.json",
  "original_topic": "AI研究综述",
  "unique_survey_title": "人工智能技术发展现状与趋势分析"
}
```

**错误响应**:
- `400 Bad Request`: 请求参数为空
- `401 Unauthorized`: 无法获取用户信息
- `500 Internal Server Error`: Pipeline管理器未初始化或处理失败

---

### 5. 获取任务状态
```http
GET /task/{task_id}
```

获取指定任务的详细状态信息。

**路径参数**:
- `task_id`: 任务ID (string)

**响应示例**:
```json
{
  "success": true,
  "task": {
    "id": "task_12345",
    "status": "running",
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:35:00Z",
    "params": {
      "topic": "AI研究综述",
      "description": "关于人工智能的综合研究",
      "output_file": "/path/to/output.json"
    },
    "progress": 65,
    "original_topic": "AI研究综述",
    "expected_survey_title": "人工智能技术发展现状与趋势分析"
  }
}
```

**任务状态枚举**:
- `pending`: 等待中
- `running`: 运行中
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

**错误响应**:
- `404 Not Found`: 任务不存在

---

### 6. 获取Pipeline状态
```http
GET /task/{task_id}/pipeline_status
```

获取指定任务相关的Pipeline详细状态。

**路径参数**:
- `task_id`: 任务ID (string)

**响应示例**:
```json
{
  "success": true,
  "task_id": "task_12345",
  "status": "running",
  "pipeline_running": true,
  "is_global_pipeline": true,
  "nodes": [
    {
      "name": "search_node",
      "is_running": true,
      "status": "运行中",
      "queue_size": 5,
      "max_queue_size": 100,
      "executing_count": 2,
      "worker_count": 4
    },
    {
      "name": "process_node",
      "is_running": true,
      "status": "运行中",
      "queue_size": 3,
      "max_queue_size": 50,
      "executing_count": 1,
      "worker_count": 2
    }
  ]
}
```

---

### 7. 获取全局Pipeline状态
```http
GET /global_pipeline_status
```

获取系统全局Pipeline状态和统计信息。

**响应示例**:
```json
{
  "success": true,
  "pipeline_initialized": true,
  "pipeline_running": true,
  "active_tasks_count": 3,
  "total_tasks_count": 15,
  "nodes": [
    {
      "name": "search_node",
      "is_running": true,
      "status": "运行中",
      "queue_size": 8,
      "max_queue_size": 100,
      "executing_count": 3,
      "worker_count": 4
    }
  ]
}
```

---

### 8. 获取任务列表
```http
GET /tasks
```

获取任务列表，支持状态过滤和数量限制。

**查询参数**:
- `status`: 状态过滤 (string, 可选)
- `limit`: 返回数量限制 (integer, 默认100)

**示例请求**:
```http
GET /tasks?status=completed&limit=20
```

**响应示例**:
```json
{
  "success": true,
  "tasks": [
    {
      "id": "task_12345",
      "status": "completed",
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T11:00:00Z",
      "params": {
        "topic": "AI研究综述"
      }
    }
  ],
  "count": 1,
  "global_pipeline_mode": true
}
```

**错误响应**:
- `400 Bad Request`: 无效的状态值

---

### 9. 获取用户任务列表
```http
GET /user/tasks
```

获取当前登录用户创建的任务列表，支持状态过滤和数量限制。

**请求头**:
```
Authorization: Bearer <token>
```

**查询参数**:
- `status`: 状态过滤 (string, 可选)
- `limit`: 返回数量限制 (integer, 默认100)

**示例请求**:
```http
GET /user/tasks?status=completed&limit=10
```

**响应示例**:
```json
{
  "success": true,
  "tasks": [
    {
      "id": "task_12345",
      "status": "completed",
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T11:00:00Z",
      "params": {
        "topic": "AI研究综述",
        "user_id": 1
      },
      "execution_seconds": 120.5,
      "start_time": "2025-01-15T10:30:30Z",
      "end_time": "2025-01-15T10:32:30Z"
    },
    {
      "id": "task_67890",
      "status": "running",
      "created_at": "2025-01-15T11:00:00Z",
      "updated_at": "2025-01-15T11:05:00Z",
      "params": {
        "topic": "机器学习算法研究",
        "user_id": 1
      }
    }
  ],
  "count": 2,
  "user_id": 1
}
```

**错误响应**:
- `400 Bad Request`: 无效的状态值
- `401 Unauthorized`: 未提供有效token或无法获取用户信息
- `500 Internal Server Error`: 服务器内部错误

---

### 10. 获取任务输出结果
```http
GET /output/{task_id}
```

获取已完成任务的输出结果，优先从数据库获取，备选从文件获取。

**路径参数**:
- `task_id`: 任务ID (string)

**响应示例（数据库来源）**:
```json
{
  "success": true,
  "content": "{\n  \"title\": \"AI研究综述\",\n  \"sections\": [...]\n}",
  "source": "database",
  "metadata": {
    "created_at": "2025-01-15T11:00:00Z",
    "title": "人工智能技术发展现状与趋势分析",
    "status": "completed"
  }
}
```

**响应示例（文件来源）**:
```json
{
  "success": true,
  "content": "{\n  \"title\": \"AI研究综述\",\n  \"sections\": [...]\n}",
  "source": "file",
  "output_file": "/path/to/output.json"
}
```

**错误响应**:
- `400 Bad Request`: 任务尚未完成
- `404 Not Found`: 任务不存在或输出结果不存在

---

### 11. 删除任务
```http
DELETE /task/{task_id}
```

删除指定的任务。

**路径参数**:
- `task_id`: 任务ID (string)

**响应示例**:
```json
{
  "success": true,
  "message": "任务 task_12345 已删除"
}
```

**错误响应**:
- `400 Bad Request`: 删除任务失败

---

## 兑换码管理接口 (Redemption Code)

### 12. 生成兑换码
```http
POST /redemption/generate
```

生成兑换码（管理员功能）。

**请求头**:
```
Authorization: Bearer <token>
```

**请求参数**:
```json
{
  "count": 5,          // 生成数量，默认1
  "uses_granted": 10   // 每个兑换码提供的使用次数，默认1
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "成功生成5个兑换码",
  "data": {
    "codes": [
      {
        "code": "ABC123DEF456",
        "uses_granted": 10
      },
      {
        "code": "XYZ789GHI012",
        "uses_granted": 10
      }
    ]
  }
}
```

---

### 13. 兑换码使用
```http
POST /redemption/redeem
```

使用兑换码增加用户使用次数。

**请求头**:
```
Authorization: Bearer <token>
```

**请求参数**:
```json
{
  "code": "ABC123DEF456"  // 兑换码，必填
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "兑换成功",
  "data": {
    "remaining_uses": 15,  // 用户当前剩余使用次数
    "added_uses": 10       // 本次兑换增加的使用次数
  }
}
```

**错误响应**:
- `400 Bad Request`: 缺少兑换码参数或兑换码无效
- `404 Not Found`: 用户不存在

---

### 14. 获取兑换历史
```http
GET /redemption/history
```

获取当前用户的兑换码使用历史。

**请求头**:
```
Authorization: Bearer <token>
```

**响应示例**:
```json
{
  "success": true,
  "message": "获取兑换历史成功",
  "data": {
    "history": [
      {
        "id": 1,
        "code": "ABC123DEF456",
        "uses_granted": 10,
        "redeemed_at": "2025-01-15T10:30:00Z"
      },
      {
        "id": 2,
        "code": "XYZ789GHI012",
        "uses_granted": 5,
        "redeemed_at": "2025-01-14T15:20:00Z"
      }
    ]
  }
}
```

---

## 系统监控接口 (System Monitoring)

### 15. 数据库统计信息
```http
GET /database/stats
```

获取数据库统计信息。

**响应示例**:
```json
{
  "success": true,
  "stats": {
    "total_surveys": 150,
    "completed_surveys": 120,
    "failed_surveys": 5,
    "database_size": "256MB",
    "collections": {
      "surveys": 150,
      "users": 50,
      "logs": 1000
    }
  }
}
```

**错误响应**:
- `503 Service Unavailable`: 数据库不可用

---

### 16. 数据库健康检查
```http
GET /database/health
```

检查数据库连接状态。

**响应示例**:
```json
{
  "success": true,
  "status": "healthy",
  "message": "数据库连接正常"
}
```

**错误响应**:
```json
{
  "success": false,
  "status": "unhealthy",
  "message": "数据库连接失败"
}
```

---

### 17. 服务健康检查
```http
GET /health
```

检查整个服务的健康状态。

**响应示例**:
```json
{
  "success": true,
  "services": {
    "redis": {
      "status": "healthy",
      "required": true
    },
    "mongodb": {
      "status": "healthy",
      "required": false
    }
  }
}
```

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未授权/token无效 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

## 通用响应格式

所有API响应都遵循以下格式：

```json
{
  "success": boolean,    // 请求是否成功
  "message": "string",   // 响应消息
  "data": object        // 响应数据（可选）
}
```

## 认证说明

除了登录和发送验证码接口外，其他接口都需要在请求头中携带JWT token：

```
Authorization: Bearer <your_jwt_token>
```

Token获取方式：调用登录接口成功后，从响应中获取token字段。

## 速率限制

- 发送验证码：每个手机号每分钟最多1次
- 其他接口：每个用户每秒最多10次请求

## 开发环境说明

当环境变量 `FLASK_ENV=dev` 时：
- 短信验证码不会真实发送，而是在响应中返回用于测试
- 某些验证可能会被跳过以便于开发调试