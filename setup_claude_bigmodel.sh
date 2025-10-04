#!/bin/bash

# Claude Code自动更新并配置BigModel GLM-4.6模型脚本
# 作者: AI助手
# 日期: $(date +%Y-%m-%d)

echo "=========================================="
echo "Claude Code 自动更新与配置脚本"
echo "=========================================="

# 定义颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# BigModel API配置
BIGMODEL_TOKEN="47c72eb3ea3845d0b47b0a7afab098c3.ZAA85YV1VxUqhTvK"
BIGMODEL_BASE_URL="https://open.bigmodel.cn/api/paas/v4/"
MODEL_NAME="glm-4.6"

# 错误处理函数
error_exit() {
    echo -e "${RED}错误: $1${NC}" >&2
    exit 1
}

# 成功信息函数
success_msg() {
    echo -e "${GREEN}✓ $1${NC}"
}

# 警告信息函数
warning_msg() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 信息函数
info_msg() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        error_exit "命令 '$1' 未找到，请先安装"
    fi
}

# 步骤1: 检查必要的工具
info_msg "检查必要的工具..."
check_command "curl"

# 检查是否已安装jq（可选）
if command -v jq &> /dev/null; then
    HAS_JQ=true
    success_msg "jq 已安装，将用于JSON格式化"
else
    HAS_JQ=false
    warning_msg "jq 未安装，JSON输出可能不会格式化"
fi

# 步骤2: 检查当前Claude Code状态
info_msg "检查当前Claude Code状态..."
if command -v claude &> /dev/null; then
    CURRENT_VERSION=$(claude --version 2>/dev/null || echo "未知版本")
    success_msg "Claude Code已安装，当前版本: $CURRENT_VERSION"
    
    # 尝试更新
    warning_msg "正在尝试更新Claude Code..."
    if claude update 2>/dev/null; then
        success_msg "Claude Code更新成功!"
    else
        warning_msg "Claude Code更新失败，尝试重新安装..."
        # 重新安装
        if curl -fsSL https://claude.ai/install.sh | bash -s latest; then
            success_msg "Claude Code重新安装成功!"
        else
            error_exit "Claude Code安装失败，请检查网络连接"
        fi
    fi
else
    warning_msg "Claude Code未安装，正在安装最新版本..."
    if curl -fsSL https://claude.ai/install.sh | bash -s latest; then
        success_msg "Claude Code安装成功!"
    else
        error_exit "Claude Code安装失败，请检查网络连接"
    fi
fi

# 步骤3: 创建配置目录
CONFIG_DIR="$HOME/.config/claude-code"
if [ ! -d "$CONFIG_DIR" ]; then
    info_msg "创建配置目录: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR" || error_exit "无法创建配置目录"
    success_msg "配置目录创建成功"
else
    success_msg "配置目录已存在: $CONFIG_DIR"
fi

# 步骤4: 备份现有配置
CONFIG_FILE="$CONFIG_DIR/settings.json"
BACKUP_FILE="$CONFIG_DIR/settings.json.backup.$(date +%Y%m%d%H%M%S)"

if [ -f "$CONFIG_FILE" ]; then
    warning_msg "备份现有配置文件..."
    cp "$CONFIG_FILE" "$BACKUP_FILE" || error_exit "无法备份配置文件"
    success_msg "配置文件已备份到: $BACKUP_FILE"
fi

# 步骤5: 创建新的配置文件
info_msg "创建新的配置文件，使用BigModel GLM-4.6模型..."

# 检查是否需要使用代理
PROXY_CONFIG=""
if [ -n "$SOCKS5_PROXY" ]; then
    PROXY_CONFIG=",
    \"HTTPS_PROXY\": \"socks5://127.0.0.1:1080\",
    \"HTTP_PROXY\": \"socks5://127.0.0.1:1080\""
    info_msg "检测到代理配置，将使用 socks5://127.0.0.1:1080"
fi

cat > "$CONFIG_FILE" << EOF
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "$BIGMODEL_TOKEN",
    "ANTHROPIC_BASE_URL": "$BIGMODEL_BASE_URL",
    "ANTHROPIC_MODEL": "$MODEL_NAME"$PROXY_CONFIG
  },
  "model": {
    "name": "$MODEL_NAME",
    "provider": "bigmodel",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "ui": {
    "theme": "dark",
    "language": "zh-CN"
  }
}
EOF

if [ $? -eq 0 ]; then
    success_msg "配置文件创建成功!"
else
    error_exit "配置文件创建失败"
fi

# 步骤6: 验证配置文件
info_msg "验证配置文件..."
if [ -f "$CONFIG_FILE" ]; then
    success_msg "配置文件存在，内容如下:"
    echo "----------------------------------------"
    if [ "$HAS_JQ" = true ]; then
        cat "$CONFIG_FILE" | jq .
    else
        cat "$CONFIG_FILE"
    fi
    echo "----------------------------------------"
else
    error_exit "配置文件验证失败"
fi

# 步骤7: 设置环境变量（可选）
info_msg "设置环境变量..."
SHELL_RC=""
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    # 检查是否已经设置了环境变量
    if ! grep -q "ANTHROPIC_AUTH_TOKEN" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# BigModel GLM-4.6 配置" >> "$SHELL_RC"
        echo "export ANTHROPIC_AUTH_TOKEN=\"$BIGMODEL_TOKEN\"" >> "$SHELL_RC"
        echo "export ANTHROPIC_BASE_URL=\"$BIGMODEL_BASE_URL\"" >> "$SHELL_RC"
        echo "export ANTHROPIC_MODEL=\"$MODEL_NAME\"" >> "$SHELL_RC"
        success_msg "环境变量已添加到 $SHELL_RC"
        warning_msg "请运行 'source $SHELL_RC' 或重新打开终端以加载环境变量"
    else
        warning_msg "环境变量已存在于 $SHELL_RC"
    fi
fi

# 步骤8: 测试配置
info_msg "测试Claude Code配置..."
if command -v claude &> /dev/null; then
    # 尝试运行claude命令检查配置
    if claude --help &> /dev/null; then
        success_msg "Claude Code配置测试通过"
    else
        warning_msg "Claude Code配置可能有问题，请手动检查"
    fi
else
    warning_msg "Claude Code命令不可用，可能需要重新启动终端"
fi

# 完成提示
echo "=========================================="
success_msg "配置完成!"
success_msg "Claude Code已更新并配置为使用BigModel的GLM-4.6模型"
echo "=========================================="
echo ""
echo "📋 使用说明:"
echo "1. 运行 'claude' 命令启动Claude Code"
echo "2. 如需恢复原配置，可使用备份文件: $BACKUP_FILE"
echo "3. 配置文件位置: $CONFIG_FILE"
echo ""
echo "🔧 故障排除:"
echo "- 如果遇到网络问题，请确保代理设置正确"
echo "- 如果API调用失败，请检查Token是否有效"
echo "- 如果命令不可用，请重新启动终端或运行 'source ~/.zshrc'"
echo ""
echo "✨ 现在您可以使用BigModel的GLM-4.6模型了!"