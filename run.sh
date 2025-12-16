#!/bin/bash

# Claude Code Review Tool - 运行脚本
# 自动检查依赖并运行 code review

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

# 检查 Claude CLI
check_claude_cli() {
    print_info "检查 Claude CLI..."
    if command_exists claude; then
        print_success "Claude CLI 已安装"
        return 0
    else
        print_warning "Claude CLI 未安装"
        print_info "安装方法: npm install -g @anthropic-ai/claude-cli"
        print_info "或访问: https://docs.anthropic.com/claude/docs/claude-cli"

        # 询问是否继续（仅生成 prompt）
        read -p "是否继续（仅生成 prompt，不调用 Claude）? [y/N] " -n 1 -r
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
${GREEN}Claude Code Review Tool${NC}

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
  --no-context                禁用仓库上下文访问（默认启用）
  -p, --prompt-only           只生成 prompt，不调用 Claude
  -h, --help                  显示此帮助信息

说明:
  默认情况下，Claude 会在目标仓库目录下运行，可以使用 Read/Grep/Glob 等工具
  访问完整代码。使用 --no-context 可禁用此功能。

示例:
  $0 -a 100027304 -b main -t feature/my-feature              # 完整分析（默认启用上下文）
  $0 -a 100027304 -b main -t feature/my-feature -m review    # 仅代码审查
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
            --no-context)
                NO_CONTEXT=true
                shift
                ;;
            -p|--prompt-only)
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

    local cmd="python3 \"$SCRIPT_DIR/claude_cr.py\""
    cmd="$cmd --appid \"$APPID\""
    cmd="$cmd --basebranch \"$BASEBRANCH\""
    cmd="$cmd --targetbranch \"$TARGETBRANCH\""
    cmd="$cmd --mode \"$MODE\""
    cmd="$cmd --search-root \"$SEARCH_ROOT\""

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
    echo -e "${GREEN}║   Claude Code Review Tool - 启动器    ║${NC}"
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
    check_claude_cli || true  # Claude CLI 是可选的（可以只生成 prompt）

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
