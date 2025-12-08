# 鉴权功能安装指南

## 1. 安装依赖

```bash
pip install python-jose[cryptography]
```

或者重新安装所有依赖：

```bash
pip install -r requirements.txt
```

## 2. 配置环境变量（可选）

在项目根目录创建或编辑 `.env` 文件：

```env
# 鉴权密码（默认：003717）
AUTH_PASSWORD=003717

# Token 过期时间（小时，默认：24）
AUTH_TOKEN_EXPIRE_HOURS=24

# JWT 密钥（生产环境请务必修改）
SECRET_KEY=your-secret-key-please-change-this-in-production
```

## 3. 重启服务

如果服务正在运行，需要重启：

```bash
# 停止当前服务（Ctrl+C）
# 然后重新启动
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 4. 测试鉴权功能

### 4.1 测试登录

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"003717\"}"
```

应该返回：
```json
{
  "success": true,
  "message": "登录成功",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_hours": 24
}
```

### 4.2 测试错误密码

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"wrong_password\"}"
```

应该返回 401 错误。

### 4.3 测试无需鉴权的 API（激活功能）

```bash
# 这个应该可以正常访问，无需 Token
curl -X POST "http://localhost:8000/api/cards/test-card-id/activate"
```

### 4.4 测试需要鉴权的 API（列表功能）

不带 Token 访问（应该失败）：
```bash
curl -X GET "http://localhost:8000/api/cards/"
```

应该返回 401 错误：
```json
{
  "detail": "未提供认证凭据"
}
```

带 Token 访问（应该成功）：
```bash
# 先登录获取 token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"003717\"}" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# 使用 token 访问
curl -X GET "http://localhost:8000/api/cards/" \
  -H "Authorization: Bearer $TOKEN"
```

## 5. API 文档

访问 Swagger UI 查看完整的 API 文档：
```
http://localhost:8000/docs
```

在 Swagger UI 中：
1. 点击右上角的 "Authorize" 按钮
2. 在弹出的对话框中输入从登录接口获取的 token
3. 点击 "Authorize" 按钮
4. 现在可以测试需要鉴权的 API 了

## 6. 权限总结

### ✅ 无需鉴权（公开访问）
- `POST /api/cards/{card_id}/activate` - 激活卡片
- `POST /api/cards/batch/activate` - 批量激活
- `POST /api/cards/{card_id}/query` - 查询卡片

### 🔒 需要鉴权（需要登录）
- 所有其他卡片管理功能
- 批量导入功能
- 消费记录查询
- 退款管理等

## 7. 故障排除

### 问题1：导入错误 `ModuleNotFoundError: No module named 'jose'`
解决方案：
```bash
pip install python-jose[cryptography]
```

### 问题2：Token 总是返回 401
检查：
1. Token 是否正确复制（包含完整字符串）
2. Token 是否已过期
3. 请求头格式是否正确：`Authorization: Bearer <token>`

### 问题3：密码正确但无法登录
检查：
1. 环境变量 `AUTH_PASSWORD` 是否正确设置
2. `.env` 文件是否在正确位置（项目根目录）
3. 服务是否重启以加载新配置

## 8. 下一步

查看完整文档：
- 鉴权功能说明：`README_AUTH.md`
- API 使用示例和安全建议
