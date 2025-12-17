#!/bin/bash

# Copilot Code Review Tool - 运行脚本
# 使用 GitHub Copilot CLI 进行代码审查

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查 Python 3
check_python() {
    print_info "检查 Python 3..."
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python 3 已安装: $PYTHON_VERSION"
        return 0
    else
        print_error "Python 3 未安装"
        print_info "请安装 Python 3: https://www.python.org/downloads/"
        return 1
    fi
}

# 检查 Copilot CLI
check_copilot_cli() {
    print_info "检查 Copilot CLI..."
    if command_exists copilot; then
        COPILOT_VERSION=$(copilot --version 2>&1 || echo "unknown")
        print_success "Copilot CLI 已安装: $COPILOT_VERSION"
        return 0
    else
        print_warning "Copilot CLI 未安装"
        print_info "安装方法: 在 VS Code 中安装 GitHub Copilot Chat 扩展"
        print_info "然后将 Copilot CLI 路径添加到 PATH:"
        print_info "  export PATH=\"\$PATH:\$HOME/Library/Application Support/Code/User/globalStorage/github.copilot-chat/copilotCli\""

        # 询问是否继续（仅生成 prompt）
        read -p "是否继续（仅生成 prompt，不调用 Copilot）? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            PROMPT_ONLY=true
            return 0
        else
            return 1
        fi
    fi
}

# 检查 Git
check_git() {
    print_info "检查 Git..."
    if command_exists git; then
        GIT_VERSION=$(git --version 2>&1 | awk '{print $3}')
        print_success "Git 已安装: $GIT_VERSION"
        return 0
    else
        print_error "Git 未安装"
        print_info "请安装 Git: https://git-scm.com/downloads"
        return 1
    fi
}

# 显示使用帮助
show_usage() {
    cat << EOF
${GREEN}Copilot Code Review Tool${NC}

用法:
  $0 [选项]

选项:
  -a, --appid APPID           应用 ID（必需）
  -b, --basebranch BRANCH     基准分支名称（必需）
  -t, --targetbranch BRANCH   目标分支名称（必需）
  -m, --mode MODE             运行模式（默认: all）
                              all      - 完整分析（同时运行 analyze、priority、review）
                              review   - 仅代码审查
                              analyze  - 仅变更解析
                              priority - 仅优先级评估
  -s, --search-root PATH      搜索根目录（默认: ~/VibeCoding/apprepo）
  -M, --model MODEL           指定 Copilot 模型（见下方可用模型列表）
  --no-context                禁用仓库上下文访问（默认启用）
  --prompt-only               只生成 prompt，不调用 Copilot
  -h, --help                  显示此帮助信息

可用模型:
  Claude 系列:
    claude-sonnet-4.5, claude-haiku-4.5, claude-opus-4.5, claude-sonnet-4
    简写: sonnet, haiku, opus
  GPT 系列:
    gpt-5.1-codex-max, gpt-5.1-codex, gpt-5.2, gpt-5.1, gpt-5
    gpt-5.1-codex-mini, gpt-5-mini, gpt-4.1
    简写: codex-max, codex
  Gemini 系列:
    gemini-3-pro-preview
    简写: gemini

说明:
  该工具使用 copilot -p 命令进行代码审查，支持三种分析模式并行执行。
  Copilot 会在目标仓库目录下运行，可以使用工具访问完整代码。

示例:
  $0 -a 100027304 -b main -t feature/my-feature              # 完整分析（默认）
  $0 -a 100027304 -b main -t feature/my-feature -m review    # 仅代码审查
  $0 -a 100027304 -b main -t feature/test -M sonnet          # 使用 Claude Sonnet 模型
  $0 -a 100027304 -b main -t feature/test -M opus            # 使用 Claude Opus 模型
  $0 -a 100027304 -b main -t feature/test -M codex-max       # 使用 GPT Codex Max 模型
  $0 -a 100027304 -b main -t feature/test -M gemini          # 使用 Gemini 模型
  $0 -a 100027304 -b main -t feature/test --prompt-only      # 只生成 prompt
  $0 -a 100027304 -b main -t feature/test --no-context       # 禁用仓库上下文

EOF
}

# 解析命令行参数
parse_args() {
    APPID=""
    BASEBRANCH=""
    TARGETBRANCH=""
    SEARCH_ROOT="$HOME/VibeCoding/apprepo"
    MODE="all"
    MODEL=""
    PROMPT_ONLY=false
    NO_CONTEXT=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--appid)
                APPID="$2"
                shift 2
                ;;
            -b|--basebranch)
                BASEBRANCH="$2"
                shift 2
                ;;
            -t|--targetbranch)
                TARGETBRANCH="$2"
                shift 2
                ;;
            -m|--mode)
                MODE="$2"
                shift 2
                ;;
            -s|--search-root)
                SEARCH_ROOT="$2"
                shift 2
                ;;
            -M|--model)
                MODEL="$2"
                shift 2
                ;;
            --no-context)
                NO_CONTEXT=true
                shift
                ;;
            --prompt-only)
                PROMPT_ONLY=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "未知选项: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # 验证必需参数
    if [[ -z "$APPID" ]] || [[ -z "$BASEBRANCH" ]] || [[ -z "$TARGETBRANCH" ]]; then
        print_error "缺少必需参数"
        show_usage
        exit 1
    fi
}

# 运行 Python 版本
run_python_version() {
    print_info "使用 Python 版本运行..."

    local cmd="python3 \"$SCRIPT_DIR/copilot_cr.py\""
    cmd="$cmd --appid \"$APPID\""
    cmd="$cmd --basebranch \"$BASEBRANCH\""
    cmd="$cmd --targetbranch \"$TARGETBRANCH\""
    cmd="$cmd --mode \"$MODE\""
    cmd="$cmd --search-root \"$SEARCH_ROOT\""

    if [[ -n "$MODEL" ]]; then
        cmd="$cmd --model \"$MODEL\""
    fi

    if [[ "$NO_CONTEXT" == true ]]; then
        cmd="$cmd --no-context"
    fi

    if [[ "$PROMPT_ONLY" == true ]]; then
        cmd="$cmd --prompt-only"
    fi

    print_info "执行命令: $cmd"
    echo ""

    eval "$cmd"
}

# 主函数
main() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Copilot Code Review Tool - 启动器    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""

    # 解析参数
    parse_args "$@"

    # 检查依赖
    print_info "开始检查依赖..."
    echo ""

    local all_deps_ok=true

    # 必需依赖
    check_python || all_deps_ok=false
    check_git || all_deps_ok=false
    check_copilot_cli || true  # Copilot CLI 是可选的（可以只生成 prompt）

    echo ""

    if [[ "$all_deps_ok" == false ]]; then
        print_error "必需依赖检查失败，请安装缺失的依赖"
        exit 1
    fi

    print_success "依赖检查完成"
    echo ""

    # 显示配置信息
    print_info "配置信息:"
    echo "  AppID: $APPID"
    echo "  Base Branch: $BASEBRANCH"
    echo "  Target Branch: $TARGETBRANCH"
    echo "  Mode: $MODE"
    echo "  Search Root: $SEARCH_ROOT"
    if [[ -n "$MODEL" ]]; then
        echo "  Model: $MODEL"
    fi
    echo "  Context: $(if [[ "$NO_CONTEXT" == true ]]; then echo "禁用"; else echo "启用（默认）"; fi)"
    echo "  Prompt Only: $PROMPT_ONLY"
    echo ""

    # 运行 Python 版本
    run_python_version
    exit $?
}

# 捕获 Ctrl+C
trap 'echo ""; print_warning "用户中断"; exit 130' INT

# 运行主函数
main "$@"
