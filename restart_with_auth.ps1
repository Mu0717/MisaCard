# 重启服务脚本（带鉴权功能）

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "MisaCard Manager - 重启服务（鉴权功能）" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# 1. 检查并安装依赖
Write-Host "[1/3] 检查依赖包..." -ForegroundColor Yellow
$joseInstalled = pip show python-jose 2>&1 | Select-String "Name: python-jose"

if (-not $joseInstalled) {
    Write-Host "  正在安装 python-jose..." -ForegroundColor Yellow
    pip install python-jose[cryptography]
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ python-jose 安装成功" -ForegroundColor Green
    } else {
        Write-Host "  ✗ python-jose 安装失败" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✓ python-jose 已安装" -ForegroundColor Green
}

Write-Host ""

# 2. 验证配置
Write-Host "[2/3] 验证配置..." -ForegroundColor Yellow

if (Test-Path ".env") {
    Write-Host "  ✓ 找到 .env 文件" -ForegroundColor Green
} else {
    Write-Host "  ⚠ 未找到 .env 文件，将使用默认配置" -ForegroundColor Yellow
    Write-Host "  默认密码: 003717" -ForegroundColor Gray
}

Write-Host ""

# 3. 启动服务
Write-Host "[3/3] 启动服务..." -ForegroundColor Yellow
Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "服务信息:" -ForegroundColor Cyan
Write-Host "  - 地址: http://0.0.0.0:8000" -ForegroundColor White
Write-Host "  - API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - 默认密码: 003717" -ForegroundColor White
Write-Host ""
Write-Host "功能权限:" -ForegroundColor Cyan
Write-Host "  ✓ 无需密码: 查询、激活" -ForegroundColor Green
Write-Host "  ✗ 需要密码: 其他所有功能" -ForegroundColor Yellow
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Gray
Write-Host ""

# 启动 uvicorn
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
