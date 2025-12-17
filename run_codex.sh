#!/bin/bash

# Codex Code Review Tool - 运行脚本
# 使用 codex review 命令进行代码审查

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

# 检查 Codex CLI
check_codex_cli() {
    print_info "检查 Codex CLI..."
    if command_exists codex; then
        CODEX_VERSION=$(codex --version 2>&1 || echo "unknown")
        print_success "Codex CLI 已安装: $CODEX_VERSION"
        return 0
    else
        print_warning "Codex CLI 未安装"
        print_info "安装方法: 参考 https://github.com/openai/codex"

        # 询问是否继续(仅创建输出目录)
        read -p "是否继续(仅创建输出目录,不执行 codex review)? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            DRY_RUN=true
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
${GREEN}Codex Code Review Tool${NC}

用法:
  $0 [选项]

选项:
  -a, --appid APPID           应用 ID(必需)
  -b, --basebranch BRANCH     基准分支名称(必需)
  -t, --targetbranch BRANCH   目标分支名称(必需)
  -s, --search-root PATH      搜索根目录(默认: ~/VibeCoding/apprepo)
  -m, --mode MODE             运行模式: all(默认), review, analyze, priority
  -M, --model MODEL           指定 Codex 模型(如 o3, gpt-4o, gpt-5.1-codex-max)
  -p, --profile PROFILE       使用预定义的 Codex Profile(如 o3)
  -r, --reasoning-effort LVL  推理努力程度: minimal, low, medium, high, xhigh
  --prompt-only               只生成 prompt,不调用 Codex
  --no-context                禁用仓库上下文访问
  -h, --help                  显示此帮助信息

说明:
  该工具使用 codex exec 命令进行代码审查,支持三种分析模式并行执行。
  codex 会在目标仓库目录下运行,自动分析与基准分支的差异。

示例:
  $0 -a 100027304 -b main -t feature/my-feature                          # 基本用法(all模式)
  $0 -a 100027304 -b main -t feature/test -m review                      # 仅代码审查
  $0 -a 100027304 -b main -t feature/test -M gpt-5.1-codex-max -r high   # 指定模型和推理程度
  $0 -a 100027304 -b main -t feature/test --profile o3                   # 使用 o3 Profile
  $0 -a 100027304 -b main -t feature/test --prompt-only                  # 只生成 prompt

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
    PROFILE=""
    REASONING_EFFORT=""
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
            -s|--search-root)
                SEARCH_ROOT="$2"
                shift 2
                ;;
            -m|--mode)
                MODE="$2"
                shift 2
                ;;
            -M|--model)
                MODEL="$2"
                shift 2
                ;;
            -p|--profile)
                PROFILE="$2"
                shift 2
                ;;
            -r|--reasoning-effort)
                REASONING_EFFORT="$2"
                shift 2
                ;;
            --prompt-only)
                PROMPT_ONLY=true
                shift
                ;;
            --no-context)
                NO_CONTEXT=true
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

    local cmd="python3 \"$SCRIPT_DIR/codex_cr.py\""
    cmd="$cmd --appid \"$APPID\""
    cmd="$cmd --basebranch \"$BASEBRANCH\""
    cmd="$cmd --targetbranch \"$TARGETBRANCH\""
    cmd="$cmd --search-root \"$SEARCH_ROOT\""
    cmd="$cmd --mode \"$MODE\""

    if [[ -n "$MODEL" ]]; then
        cmd="$cmd --model \"$MODEL\""
    fi

    if [[ -n "$PROFILE" ]]; then
        cmd="$cmd --profile \"$PROFILE\""
    fi

    if [[ -n "$REASONING_EFFORT" ]]; then
        cmd="$cmd --reasoning-effort \"$REASONING_EFFORT\""
    fi

    if [[ "$PROMPT_ONLY" == true ]]; then
        cmd="$cmd --prompt-only"
    fi

    if [[ "$NO_CONTEXT" == true ]]; then
        cmd="$cmd --no-context"
    fi

    print_info "执行命令: $cmd"
    echo ""

    eval "$cmd"
}

# 主函数
main() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Codex Code Review Tool - 启动器     ║${NC}"
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
    check_codex_cli || true  # Codex CLI 是可选的(可以只创建输出目录)

    echo ""

    if [[ "$all_deps_ok" == false ]]; then
        print_error "必需依赖检查失败,请安装缺失的依赖"
        exit 1
    fi

    print_success "依赖检查完成"
    echo ""

    # 显示配置信息
    print_info "配置信息:"
    echo "  AppID: $APPID"
    echo "  Base Branch: $BASEBRANCH"
    echo "  Target Branch: $TARGETBRANCH"
    echo "  Search Root: $SEARCH_ROOT"
    echo "  Mode: $MODE"
    if [[ -n "$MODEL" ]]; then
        echo "  Model: $MODEL"
    fi
    if [[ -n "$PROFILE" ]]; then
        echo "  Profile: $PROFILE"
    fi
    if [[ -n "$REASONING_EFFORT" ]]; then
        echo "  Reasoning Effort: $REASONING_EFFORT"
    fi
    echo "  Prompt Only: $PROMPT_ONLY"
    echo "  No Context: $NO_CONTEXT"
    echo ""

    # 运行 Python 版本
    run_python_version
    exit $?
}

# 捕获 Ctrl+C
trap 'echo ""; print_warning "用户中断"; exit 130' INT

# 运行主函数
main "$@"
