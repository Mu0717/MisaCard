# 密码鉴权功能说明

## 概述
本系统实现了基于 JWT Token 的密码鉴权功能，保护敏感 API 端点。

## 默认密码
- 默认密码：`003717`
- 可通过环境变量 `AUTH_PASSWORD` 修改

## 功能权限

### 无需鉴权的功能（公开访问）
1. **卡片激活**
   - `POST /api/cards/{card_id}/activate` - 单张卡片激活
   - `POST /api/cards/batch/activate` - 批量激活卡片

2. **卡片查询**
   - `POST /api/cards/{card_id}/query` - 查询卡片信息

### 需要鉴权的功能（需要登录）
1. **卡片管理**
   - `POST /api/cards/` - 创建新卡片
   - `GET /api/cards/` - 获取卡片列表
   - `GET /api/cards/{card_id}` - 获取单个卡片详情
   - `PUT /api/cards/{card_id}` - 更新卡片信息
   - `DELETE /api/cards/{card_id}` - 删除卡片

2. **卡片操作**
   - `POST /api/cards/{card_id}/refund` - 切换退款状态
   - `POST /api/cards/{card_id}/mark-used` - 切换使用状态
   - `GET /api/cards/{card_id}/logs` - 获取激活日志
   - `GET /api/cards/{card_id}/transactions` - 获取消费记录
   - `GET /api/cards/batch/unreturned-card-numbers` - 获取未退款卡号

3. **批量导入**
   - `POST /api/import/text` - 从文本导入卡片
   - `POST /api/import/json` - 从 JSON 导入卡片

## API 使用方法

### 1. 登录获取 Token

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"password": "003717"}'
```

响应示例：
```json
{
  "success": true,
  "message": "登录成功",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_hours": 24
}
```

### 2. 使用 Token 访问受保护的 API

在请求头中添加 `Authorization: Bearer <token>`：

```bash
curl -X GET "http://localhost:8000/api/cards/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. 验证 Token 是否有效

```bash
curl -X GET "http://localhost:8000/api/auth/verify" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 4. 登出（客户端删除 Token）

```bash
curl -X POST "http://localhost:8000/api/auth/logout"
```

## 错误响应

### 未提供 Token
```json
{
  "detail": "未提供认证凭据"
}
```
HTTP 状态码：401

### Token 无效或已过期
```json
{
  "detail": "无效的认证凭据或已过期"
}
```
HTTP 状态码：401

### 密码错误
```json
{
  "detail": "密码错误"
}
```
HTTP 状态码：401

## 环境变量配置

在 `.env` 文件中配置：

```env
# 鉴权密码（默认：003717）
AUTH_PASSWORD=003717

# Token 过期时间（小时，默认：24）
AUTH_TOKEN_EXPIRE_HOURS=24

# JWT 密钥（生产环境请务必修改）
SECRET_KEY=your-secret-key-change-in-production
```

## 前端集成示例

### JavaScript/TypeScript

```javascript
// 登录
async function login(password) {
  const response = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ password }),
  });
  
  const data = await response.json();
  if (data.success) {
    // 保存 token 到 localStorage
    localStorage.setItem('access_token', data.access_token);
    return true;
  }
  return false;
}

// 调用受保护的 API
async function getCards() {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('http://localhost:8000/api/cards/', {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });
  
  if (response.status === 401) {
    // Token 过期，需要重新登录
    console.error('需要重新登录');
    return null;
  }
  
  return await response.json();
}

// 调用无需鉴权的 API（激活）
async function activateCard(cardId) {
  const response = await fetch(`http://localhost:8000/api/cards/${cardId}/activate`, {
    method: 'POST',
  });
  return await response.json();
}
```

## 安全建议

1. **生产环境配置**
   - 务必修改 `SECRET_KEY` 为强随机字符串
   - 使用强密码替换默认密码 `003717`
   - 启用 HTTPS 传输加密

2. **Token 管理**
   - 前端安全存储 Token（使用 HttpOnly Cookie 或加密的 localStorage）
   - Token 过期后自动跳转到登录页
   - 退出登录时清除本地 Token

3. **密码安全**
   - 定期更换密码
   - 不要在代码中硬编码密码
   - 使用环境变量管理敏感配置

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

在 Swagger UI 中可以点击右上角的 "Authorize" 按钮输入 Token 进行测试。
