# 🚀 快速开始 - 密码鉴权功能

## ⚡ 一键启动

### Windows (PowerShell)
```powershell
.\restart_with_auth.ps1
```

### Linux/Mac (Bash)
```bash
chmod +x restart_with_auth.sh
./restart_with_auth.sh
```

---

## 📋 手动启动（3步）

### 步骤 1: 安装依赖
```bash
pip install python-jose[cryptography]
```

### 步骤 2: 停止旧服务
在运行 uvicorn 的终端按 `Ctrl+C`

### 步骤 3: 启动服务
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🎯 功能说明

### 默认密码
```
003717
```

### 🔓 无需密码的功能
- ✅ 查询卡片信息
- ✅ 激活卡片（单个/批量）

### 🔒 需要密码的功能
- ❌ 创建/编辑/删除卡片
- ❌ 查看卡片列表
- ❌ 批量导入
- ❌ 消费记录查询
- ❌ 退款管理
- ❌ 所有其他管理功能

---

## 🧪 快速测试

### 1. 访问 API 文档
浏览器打开：http://localhost:8000/docs

### 2. 测试登录
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"003717\"}"
```

### 3. 运行自动化测试
```bash
python test_auth.py
```

---

## 💡 使用示例

### 场景 1: 激活卡片（无需登录）
```bash
# 直接激活，无需密码
curl -X POST "http://localhost:8000/api/cards/mio-xxx-xxx/activate"
```

### 场景 2: 查看卡片列表（需要登录）

**步骤 1: 登录获取 Token**
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"password": "003717"}'
```

**响应：**
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**步骤 2: 使用 Token 访问**
```bash
curl -X GET "http://localhost:8000/api/cards/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## 🌐 前端集成

### JavaScript 示例
```javascript
// 1. 登录
const loginResponse = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ password: '003717' })
});

const { access_token } = await loginResponse.json();

// 2. 保存 Token
localStorage.setItem('token', access_token);

// 3. 使用 Token 访问受保护的 API
const token = localStorage.getItem('token');
const response = await fetch('/api/cards/', {
  headers: { 'Authorization': `Bearer ${token}` }
});

// 4. 访问公开 API（无需 Token）
await fetch('/api/cards/mio-xxx/activate', { method: 'POST' });
```

---

## 📚 完整文档

- **AUTH_SUMMARY.md** - 功能实现总结
- **README_AUTH.md** - 详细使用文档
- **INSTALL_AUTH.md** - 安装和测试指南
- **启动说明.md** - 重启服务说明

---

## ❓ 常见问题

### Q: 如何修改默认密码？
在 `.env` 文件中设置：
```env
AUTH_PASSWORD=your_new_password
```

### Q: Token 有效期多久？
默认 24 小时，可在 `.env` 中修改：
```env
AUTH_TOKEN_EXPIRE_HOURS=48
```

### Q: 忘记密码怎么办？
查看 `.env` 文件或使用默认密码 `003717`

### Q: 为什么访问列表返回 401？
需要先登录获取 Token，然后在请求头中添加：
```
Authorization: Bearer <your_token>
```

---

## ✅ 检查清单

启动成功后检查：
- [ ] 访问 http://localhost:8000/docs 能看到 `/api/auth` 接口
- [ ] 登录接口返回 Token
- [ ] 激活功能无需 Token 可以访问
- [ ] 列表功能需要 Token 才能访问

---

**一切就绪！开始使用密码鉴权功能吧！** 🎉
