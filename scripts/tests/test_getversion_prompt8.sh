#!/usr/bin/env bash
#
# Prompt8 验收：验证 scripts/package/getversion.sh 在
#   - 无 tag（仅有 commit）时：pyproject 版本 + .dev-<sha>
#   - 无 git 命令 / 无 .git 时：pyproject + +nogit，非空且不崩溃
#   - CI 环境变量 tag 优先
#   - 内置 --self-test 通过
#
# 用法（在 activitywatch 仓库根目录或任意目录）：
#   bash scripts/tests/test_getversion_prompt8.sh
#   或
#   ACTIVITYWATCH_ROOT=/path/to/activitywatch bash scripts/tests/test_getversion_prompt8.sh
#
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_RUN=0
TESTS_FAIL=0

fail() {
  echo -e "${RED}[FAIL]${NC} $*" >&2
  TESTS_FAIL=$((TESTS_FAIL + 1))
}

pass() {
  echo -e "${GREEN}[PASS]${NC} $*"
  TESTS_RUN=$((TESTS_RUN + 1))
}

info() {
  echo -e "${YELLOW}[INFO]${NC} $*"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${ACTIVITYWATCH_ROOT:-}" ]]; then
  AW_ROOT="$(cd "$ACTIVITYWATCH_ROOT" && pwd)"
else
  AW_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

GETVERSION="$AW_ROOT/scripts/package/getversion.sh"
PYPROJECT="$AW_ROOT/pyproject.toml"

if [[ ! -x "$GETVERSION" ]] && [[ -f "$GETVERSION" ]]; then
  :
fi

if [[ ! -f "$GETVERSION" ]]; then
  echo "找不到 getversion.sh: $GETVERSION" >&2
  exit 2
fi

if [[ ! -f "$PYPROJECT" ]]; then
  echo "找不到 pyproject.toml: $PYPROJECT" >&2
  exit 2
fi

EXPECTED_PY_VER=""
EXPECTED_PY_VER="$(grep -E '^version\s*=' "$PYPROJECT" | head -1 | sed 's/.*"\([^"]*\)".*/\1/')"

# ---------------------------------------------------------------------------
test_builtin_self_test() {
  info "运行 getversion.sh --self-test"
  if bash "$GETVERSION" --self-test; then
    pass "内置 --self-test 通过"
  else
    fail "内置 --self-test 失败"
  fi
}

# ---------------------------------------------------------------------------
test_ci_tag_priority() {
  info "GITHUB_REF_NAME 优先于本地 git（模拟 CI tag 构建）"
  local out
  out="$(cd "$AW_ROOT" && env -i \
    HOME="${HOME:-/tmp}" \
    PATH="${PATH:-/usr/bin:/bin}" \
    GITHUB_REF_NAME="v9.8.7" \
    bash "$GETVERSION" --display)"
  if [[ "$out" == "9.8.7" ]]; then
    pass "GITHUB_REF_NAME=v9.8.7 → DISPLAY=9.8.7"
  else
    fail "期望 DISPLAY=9.8.7，实际: $out"
  fi
}

# ---------------------------------------------------------------------------
test_no_git_tree_pyproject_nogit() {
  info "无 .git（非仓库目录）：应得到 pyproject +nogit；并单独验证「PATH 中无 git」亦同路径"
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/aw-getversion-p8-nogit.XXXXXX")"
  mkdir -p "$tmp/scripts/package"
  cp "$PYPROJECT" "$tmp/"
  cp "$GETVERSION" "$tmp/scripts/package/getversion.sh"

  local out tag out_nogitcmd
  # 典型场景：有 git 可执行文件但当前目录不是仓库 → has_git 为假 → +nogit
  out="$(cd "$tmp" && env -i HOME="${HOME:-/tmp}" PATH="/usr/bin:/bin" /bin/bash scripts/package/getversion.sh --display 2>/dev/null || true)"
  tag="$(cd "$tmp" && env -i HOME="${HOME:-/tmp}" PATH="/usr/bin:/bin" /bin/bash scripts/package/getversion.sh --tag 2>/dev/null || true)"
  # 补充：PATH 中不包含 git，但包含 grep/sed/head/wc/cut（getversion 依赖），模拟「无 git 命令」
  local fakepath="$tmp/fakepath"
  mkdir -p "$fakepath"
  for cmd in grep sed head wc cut; do
    if command -v "$cmd" &>/dev/null; then
      ln -sf "$(command -v "$cmd")" "$fakepath/$cmd"
    fi
  done
  out_nogitcmd="$(cd "$tmp" && env -i HOME="${HOME:-/tmp}" PATH="$fakepath" /bin/bash scripts/package/getversion.sh --display 2>/dev/null || true)"

  rm -rf "$tmp"

  if [[ -z "$out" ]]; then
    fail "无 .git 时 --display 为空"
    return
  fi

  if [[ "$out" != *"+nogit"* ]]; then
    fail "期望 display 含 '+nogit'，实际: $out"
    return
  fi

  if [[ "$tag" != v*"+nogit"* ]]; then
    fail "期望 --tag 形如 v<ver>+nogit，实际: $tag"
    return
  fi

  if [[ -z "$out_nogitcmd" ]] || [[ "$out_nogitcmd" != *"+nogit"* ]]; then
    fail "PATH 无 git 时期望仍为 +nogit，实际: '$out_nogitcmd'"
    return
  fi

  pass "非仓库目录 +nogit：display='$out'（无 git 在 PATH 时一致）"
}

# ---------------------------------------------------------------------------
test_git_repo_no_tags_dev_sha() {
  info "有 git、无 tag：应得到 ${EXPECTED_PY_VER}.dev-<sha>（不得为空）"
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/aw-getversion-p8-dev.XXXXXX")"
  mkdir -p "$tmp/scripts/package"
  cp "$PYPROJECT" "$tmp/"
  cp "$GETVERSION" "$tmp/scripts/package/getversion.sh"

  (
    cd "$tmp"
    git init -q
    git config user.email "test@example.com"
    git config user.name "test"
    git add pyproject.toml
    git commit -q -m "init"
  )

  local out
  out="$(
    cd "$tmp" && env -i \
      HOME="${HOME:-/tmp}" \
      PATH="${PATH:-/usr/bin:/bin}" \
      bash scripts/package/getversion.sh --display
  )"

  rm -rf "$tmp"

  if [[ -z "$out" ]]; then
    fail "无 tag 仓库下 --display 为空"
    return
  fi

  if [[ "$out" != "${EXPECTED_PY_VER}.dev-"* ]]; then
    fail "期望以 ${EXPECTED_PY_VER}.dev- 开头，实际: $out"
    return
  fi

  local sha_part="${out#*.dev-}"
  if [[ ${#sha_part} -lt 4 ]]; then
    fail "dev 后缀过短: $out"
    return
  fi

  pass "无 tag：display='$out'"
}

# ---------------------------------------------------------------------------
test_current_repo_nonempty() {
  info "当前仓库：--display / --tag 非空且退出码 0"
  local d t
  d="$(cd "$AW_ROOT" && bash "$GETVERSION" --display)"
  t="$(cd "$AW_ROOT" && bash "$GETVERSION" --tag)"
  if [[ -n "$d" && -n "$t" ]]; then
    pass "当前仓库 version: display='$d' tag='$t'"
  else
    fail "当前仓库输出为空 display='$d' tag='$t'"
  fi
}

# ---------------------------------------------------------------------------
test_workflow_fetch_depth_documented() {
  info "CI：build.yml 使用 fetch-depth: 0（无需脚本内再 fetch tag）"
  local wf="$AW_ROOT/.github/workflows/build.yml"
  if [[ -f "$wf" ]] && grep -q 'fetch-depth:\s*0' "$wf"; then
    pass "build.yml 含 fetch-depth: 0"
  else
    fail "未在 $wf 找到 fetch-depth: 0（请核对 CI 策略）"
  fi
}

# ---------------------------------------------------------------------------
main() {
  echo "=========================================="
  echo "Prompt8 getversion 验收脚本"
  echo "ACTIVITYWATCH_ROOT=$AW_ROOT"
  echo "=========================================="
  echo ""

  test_current_repo_nonempty
  test_builtin_self_test
  test_ci_tag_priority
  test_no_git_tree_pyproject_nogit
  test_git_repo_no_tags_dev_sha
  test_workflow_fetch_depth_documented

  echo ""
  echo "=========================================="
  if [[ $TESTS_FAIL -eq 0 ]]; then
    echo -e "${GREEN}全部通过${NC}（$TESTS_RUN 项）"
    exit 0
  else
    echo -e "${RED}失败 ${TESTS_FAIL} 项${NC}（通过 $TESTS_RUN 项）"
    exit 1
  fi
}

main "$@"
