#!/usr/bin/env bash
# 定时刷新「github.io 主站点」的交互式热力图页面。
#
# 干嘛的：取数（GitHub CLI）→ 重绘单文件网页 → 页面有变化才提交并推送到站点仓库。
# 统计口径：只数 commit 次数，不碰仓库名、议题、合并请求的标题。
#
# 站点在哪：默认 /mnt/d/Projects/主页设计/bihongcue876.github.io（可用 HEATMAP_SITE_REPO 覆盖）
# 首页 index.html 里有一个迷你盘和跳转链接，每次刷新一并重画。
#
# 用法：
#   scripts/update.sh              # 正常跑（有变化就 commit & push）
#   scripts/update.sh --dry        # 只重绘 + 看 diff，不 commit / 不 push
#   scripts/update.sh --no-push    # 同上（--dry 的别名，给 refresh.cmd 用）
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${HEATMAP_SITE_REPO:-/mnt/d/Projects/主页设计/bihongcue876.github.io}"
OUT="$SITE/heatmap/index.html"
LOG="$REPO/.heatmap.log"
LOCK="/tmp/heatmap-refresh.lock"
LOGIN="${HEATMAP_LOGIN:-bihongcue876}"

case "${1:-}" in
  --dry|--no-push) DRY_RUN=1 ;;
esac

# 同一时间只允许一个实例（WSL cron 与 Windows 任务重复触发时也一样）
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date -Is) 已在运行，跳过" >>"$LOG"
  exit 0
fi

log() { echo "$(date -Is) $*" >>"$LOG"; }
log "--- start ($SITE)"

# gh 不在非交互 PATH 里的情况兜底
export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"

if [ ! -d "$SITE/.git" ]; then
  log "!! 站点仓库还不存在：$SITE"
  log "   先建仓库：gh repo create $LOGIN.github.io --public --clone"
  log "   再把这个脚本的 HEATMAP_SITE_REPO 指到它的路径"
  exit 1
fi

if ! gh auth token >/dev/null 2>&1; then
  log "!! gh 还没登录（跑一次 gh auth login）"; exit 1
fi

# git 在 /mnt/d 上容易误报 filemode 变更
GIT="git -c core.fileMode=false"

# 1) 生成单文件交互页（数据内联，不依赖任何外部资源）
if ! python3 "$REPO/scripts/build_site.py" --login "$LOGIN" --gh native \
     --out "$OUT" --json-out "$SITE/heatmap-data.json" >>"$LOG" 2>&1; then
  log "!! 页面渲染失败，见下方输出"; exit 1
fi

# 1b) 首页那个迷你热力图也跟着最新数据重画
if ! python3 "$REPO/scripts/build_home_widget.py" >>"$LOG" 2>&1; then
  log "!! 首页组件渲染失败，见上方输出"; exit 1
fi

# 2) 有变化才提交
changed() { $GIT -C "$SITE" status --porcelain -- heatmap/index.html heatmap-data.json index.html | grep -q . ; }
if ! changed; then
  log "无变化，结束"; exit 0
fi

if [ "${DRY_RUN:-0}" = "1" ]; then
  log "DRY_RUN：有变化但不提交"
  $GIT -C "$SITE" --no-pager diff --stat -- heatmap/index.html heatmap-data.json >>"$LOG" 2>&1 || true
  exit 0
fi

# 3) 提交 + 推送（失败也不会卡住下一次运行）
$GIT -C "$SITE" add heatmap/index.html heatmap-data.json index.html
$GIT -C "$SITE" -c user.name="heatmap-bot" \
     -c user.email="heatmap-bot@users.noreply.github.com" \
     commit -q -m "更新热力图（$(date +%F)）" || true
$GIT -C "$SITE" pull --rebase --autostash -q >>"$LOG" 2>&1 || log "pull 失败，继续尝试 push"
if $GIT -C "$SITE" push -q >>"$LOG" 2>&1; then
  log "已推送 $(git -C "$SITE" log -1 --pretty=%h)"
else
  log "!! push 失败（检查 gh auth setup-git / 权限）"
  exit 1
fi

# 日志留最近 400 行
if [ -f "$LOG" ] && [ "$(wc -l <"$LOG")" -gt 400 ]; then
  tail -n 400 "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
