#!/bin/bash
#
# MisaCard2 服务器部署/更新脚本
# 用于在 Linux 服务器上部署和更新应用
# 支持虚拟环境，兼容 Ubuntu 23.04+/Debian 12+
#
# 使用方法:
#   chmod +x deploy.sh
#   ./deploy.sh
#

set -e  # 遇到错误立即退出

echo "============================================================"
echo "       MisaCard2 服务器部署脚本"
echo "============================================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 工作目录: $SCRIPT_DIR"
echo ""

# 虚拟环境目录
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON="python3"
PIP="pip3"

# 检查并设置虚拟环境
setup_venv() {
    echo "🐍 设置 Python 虚拟环境..."
    
    # 检查虚拟环境是否存在
    if [ ! -d "$VENV_DIR" ]; then
        echo "  创建虚拟环境: $VENV_DIR"
        python3 -m venv "$VENV_DIR"
        echo "  ✓ 虚拟环境创建成功"
    else
        echo "  ✓ 虚拟环境已存在"
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    PYTHON="$VENV_DIR/bin/python"
    PIP="$VENV_DIR/bin/pip"
    
    echo "  ✓ 虚拟环境已激活"
    echo "  Python: $($PYTHON --version)"
    echo ""
}

# 检查是否安装了必要的工具
check_requirements() {
    echo "🔍 检查系统环境..."
    
    # 检查 Python3
    if ! command -v python3 &> /dev/null; then
        echo "❌ 错误: 未安装 Python3"
        exit 1
    fi
    echo "✓ 系统 Python3: $(python3 --version)"
    
    # 检查 python3-venv (Ubuntu/Debian 需要)
    if ! python3 -m venv --help &> /dev/null 2>&1; then
        echo "⚠️  未安装 python3-venv，尝试安装..."
        apt-get update && apt-get install -y python3-venv python3-full || {
            echo "❌ 请手动安装: sudo apt install python3-venv python3-full"
            exit 1
        }
    fi
    
    # 检查 git (可选)
    if command -v git &> /dev/null; then
        echo "✓ Git: $(git --version)"
    fi
    
    echo ""
}

# 备份数据库
backup_database() {
    echo "💾 备份数据库..."
    
    DB_FILE="data/cards.db"
    BACKUP_DIR="backups"
    
    if [ -f "$DB_FILE" ]; then
        mkdir -p "$BACKUP_DIR"
        BACKUP_NAME="cards_$(date +%Y%m%d_%H%M%S).db"
        cp "$DB_FILE" "$BACKUP_DIR/$BACKUP_NAME"
        echo "✓ 数据库已备份至: $BACKUP_DIR/$BACKUP_NAME"
    else
        echo "⚠️  数据库文件不存在，跳过备份"
    fi
    
    echo ""
}

# 拉取最新代码 (如果是 git 仓库)
pull_latest_code() {
    if [ -d ".git" ]; then
        echo "📥 拉取最新代码..."
        
        # 保存本地修改
        git stash push -m "deploy-stash-$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
        
        # 拉取代码
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || echo "⚠️  无法拉取代码，使用本地版本"
        
        echo ""
    fi
}

# 安装/更新依赖 (使用虚拟环境)
install_dependencies() {
    echo "📦 安装/更新依赖..."
    
    if [ -f "requirements.txt" ]; then
        # 升级 pip
        $PIP install --upgrade pip -q
        
        # 安装依赖
        $PIP install -r requirements.txt -q
        echo "✓ 依赖安装完成"
    else
        echo "⚠️  未找到 requirements.txt，跳过依赖安装"
    fi
    
    echo ""
}

# 运行数据库迁移
run_migrations() {
    echo "🔄 运行数据库迁移..."
    
    # 确保 data 目录存在
    mkdir -p data
    
    # 运行卡头字段迁移
    if [ -f "migrate_add_card_header_field.py" ]; then
        $PYTHON migrate_add_card_header_field.py
    fi
    
    # 运行售卖字段迁移 (如果存在)
    if [ -f "migrate_add_sold_field.py" ]; then
        $PYTHON migrate_add_sold_field.py
    fi
    
    echo ""
}

# 停止旧服务
stop_service() {
    echo "🛑 停止旧服务..."
    
    # 尝试通过 PID 文件停止
    if [ -f "app.pid" ]; then
        OLD_PID=$(cat app.pid)
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill "$OLD_PID"
            echo "✓ 已停止旧服务 (PID: $OLD_PID)"
            sleep 2
        fi
        rm -f app.pid
    fi
    
    # 尝试通过端口查找并停止
    if command -v lsof &> /dev/null; then
        PID=$(lsof -ti:8000 2>/dev/null || true)
        if [ -n "$PID" ]; then
            kill "$PID" 2>/dev/null || true
            echo "✓ 已停止端口 8000 上的服务"
            sleep 2
        fi
    fi
    
    echo ""
}

# 启动服务 (使用虚拟环境)
start_service() {
    echo "🚀 启动服务..."
    
    # 创建日志目录
    mkdir -p logs
    
    # 使用虚拟环境中的 uvicorn 后台启动
    nohup $PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &
    
    # 保存 PID
    echo $! > app.pid
    
    sleep 2
    
    # 检查是否启动成功
    if [ -f "app.pid" ] && kill -0 $(cat app.pid) 2>/dev/null; then
        echo "✓ 服务已启动 (PID: $(cat app.pid))"
        echo "✓ 日志文件: logs/app.log"
        echo "✓ 访问地址: http://localhost:8000"
    else
        echo "❌ 服务启动失败，请检查日志:"
        tail -20 logs/app.log 2>/dev/null || echo "无法读取日志"
        exit 1
    fi
    
    echo ""
}

# Docker 部署方式
deploy_docker() {
    echo "🐳 使用 Docker 部署..."
    
    if ! command -v docker &> /dev/null; then
        echo "❌ 错误: 未安装 Docker"
        return 1
    fi
    
    # 停止旧容器
    docker-compose down 2>/dev/null || docker compose down 2>/dev/null || true
    
    # 构建并启动
    docker-compose up -d --build 2>/dev/null || docker compose up -d --build
    
    echo "✓ Docker 容器已启动"
    echo ""
}

# 显示服务状态
show_status() {
    echo "============================================================"
    echo "       部署完成！"
    echo "============================================================"
    echo ""
    echo "📊 服务状态:"
    
    if [ -f "app.pid" ]; then
        PID=$(cat app.pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo "  ✓ 服务运行中 (PID: $PID)"
        else
            echo "  ⚠️  服务可能未运行"
        fi
    fi
    
    echo ""
    echo "📋 常用命令:"
    echo "  查看日志: tail -f logs/app.log"
    echo "  停止服务: ./deploy.sh stop"
    echo "  重启服务: ./deploy.sh restart"
    echo "  仅迁移DB: ./deploy.sh migrate"
    echo ""
    echo "🐍 虚拟环境:"
    echo "  激活: source venv/bin/activate"
    echo "  退出: deactivate"
    echo ""
    echo "============================================================"
}

# 主函数
main() {
    # 创建日志目录
    mkdir -p logs
    
    # 检查是否使用 Docker
    if [ "$1" = "docker" ] || [ -f "docker-compose.yml" ] && [ "$1" != "standard" ]; then
        if [ -f "docker-compose.yml" ] && command -v docker &> /dev/null; then
            backup_database
            deploy_docker
            echo "✓ Docker 部署完成"
            exit 0
        fi
    fi
    
    # 标准部署流程
    check_requirements
    setup_venv
    backup_database
    pull_latest_code
    install_dependencies
    run_migrations
    stop_service
    start_service
    show_status
}

# 处理命令行参数
case "$1" in
    "docker")
        echo "使用 Docker 模式部署..."
        main docker
        ;;
    "migrate")
        echo "仅执行数据库迁移..."
        check_requirements
        setup_venv
        backup_database
        run_migrations
        echo "✓ 迁移完成"
        ;;
    "restart")
        echo "重启服务..."
        setup_venv
        stop_service
        start_service
        ;;
    "stop")
        echo "停止服务..."
        stop_service
        echo "✓ 服务已停止"
        ;;
    "status")
        show_status
        ;;
    "install")
        echo "仅安装依赖..."
        check_requirements
        setup_venv
        install_dependencies
        echo "✓ 依赖安装完成"
        ;;
    "help"|"-h"|"--help")
        echo "用法: ./deploy.sh [命令]"
        echo ""
        echo "命令:"
        echo "  (无)      完整部署流程"
        echo "  docker    使用 Docker 部署"
        echo "  migrate   仅执行数据库迁移"
        echo "  install   仅安装依赖"
        echo "  restart   重启服务"
        echo "  stop      停止服务"
        echo "  status    查看服务状态"
        echo "  help      显示帮助信息"
        echo ""
        echo "注意: 脚本会自动创建虚拟环境(venv)来管理Python依赖"
        ;;
    *)
        main standard
        ;;
esac
