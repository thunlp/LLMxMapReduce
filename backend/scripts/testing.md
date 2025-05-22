# API 测试指南

本文档介绍如何测试兑换码相关的 API 接口，包括生成兑换码、使用兑换码和获取兑换历史。由于这些接口需要 JWT 认证，我们提供了几种方法来进行测试。

## 前提条件

- Python 3.6+
- 安装了项目依赖（`pip install -r requirements.txt`）
- 运行中的后端服务器（通过 `python run.py` 启动）

## 1. 使用测试数据脚本

为了测试这些需要认证的 API，我们提供了一个脚本来创建测试用户和测试兑换码：

```bash
# 运行脚本创建测试数据
python setup_test_data.py
```

这个脚本会执行以下操作：
- 创建一个测试用户（手机号：13829816170）
- 为测试用户生成 JWT 令牌
- 创建一个测试兑换码
- 生成测试 API 的 curl 命令
- 创建一个测试配置文件 `test_config.json`，用于其他测试工具

脚本会输出 JWT 令牌和测试用的 curl 命令，您可以直接复制这些命令来测试 API。

## 2. 使用手动测试脚本

我们还提供了一个手动测试脚本，它会自动请求所有兑换码相关的 API：

```bash
# 运行手动测试脚本
python manual_test_api.py
```

这个脚本会依次测试以下 API：
- 生成兑换码
- 使用兑换码
- 获取兑换历史

它会使用 `test_config.json` 中的测试数据，所以请先运行 `setup_test_data.py`。

## 3. 使用单元测试

对于更系统化的测试，我们提供了单元测试：

```bash
# 运行单元测试
python test_redemption_api.py
```

这个测试使用内存数据库，不会影响您的实际数据库。它会测试所有兑换码相关的功能，包括创建、使用和查询历史记录。

## 4. 使用 Postman 或其他 API 工具测试

您还可以使用 Postman 或其他 API 测试工具：

1. 运行 `setup_test_data.py` 生成测试配置
2. 打开 `test_config.json` 获取 JWT 令牌
3. 在测试工具中设置请求头：`Authorization: Bearer <您的JWT令牌>`

### API 端点

- 生成兑换码：`POST /api/redemption/generate`
  - 请求体：`{"count": 2, "uses_granted": 3}`

- 使用兑换码：`POST /api/redemption/redeem`
  - 请求体：`{"code": "TEST1234567890"}`

- 获取兑换历史：`GET /api/redemption/history`

## 5. 使用 curl 命令测试

您可以使用 `setup_test_data.py` 输出的 curl 命令直接测试 API。例如：

```bash
# 生成兑换码
curl -X POST http://localhost:5001/api/redemption/generate -H "Authorization: Bearer <JWT令牌>" -H "Content-Type: application/json" -d '{"count": 2, "uses_granted": 5}'

# 使用兑换码
curl -X POST http://localhost:5001/api/redemption/redeem -H "Authorization: Bearer <JWT令牌>" -H "Content-Type: application/json" -d '{"code": "TEST1234567890"}'

# 获取兑换历史
curl -X GET http://localhost:5001/api/redemption/history -H "Authorization: Bearer <JWT令牌>"
``` 