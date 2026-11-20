#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
heatmap.py — 生成"只有格子、没有内容"的贡献热力图 SVG。

设计前提（隐私）：
  输出的 SVG 里只有 <date, count>，不包含仓库名、commit message、issue 标题、
  分支名、作者名。第三方看不到任何"干了什么"，只能看到"某天有几笔"。

两种数据源：
  1) local  (默认) —— 扫描本机 git 仓库的提交历史，自己数。
     * 不依赖 GitHub 的贡献日历（你的公开日历现在是空的，见 docs/heatmap.md）
     * 只统计 commit，天然不含 issue / PR / review
     * 跨仓库按 commit sha 去重（clone / fork 不会翻倍）
  2) github —— 读 GitHub GraphQL 贡献日历（需要你自己的 token）。
     * 方便自动化，但会被 GitHub 的"私密贡献"开关和邮箱验证状态卡住

用法：
  python scripts/heatmap.py                                     # 本机当前目录往下的仓库
  python scripts/heatmap.py --roots D:/Projects --weeks 53
  python scripts/heatmap.py --source github --token-env HEATMAP_TOKEN
  python scripts/heatmap.py --summary                            # 先看每天/每邮箱的统计

输出（默认写到 ./assets/）：
  heatmap-light.svg / heatmap-dark.svg
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

# ---------------------------------------------------------------- git 扫描

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pypiche__", "dist",
    "build", "target", ".next", ".nuxt", "vendor", ".idea", ".vscode",
}

def find_repos(roots, max_depth):
    repos = []
    for root in roots:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > max_depth:
                dirnames[:] = []
                continue
            has_git = ".git" in dirnames or ".git" in filenames
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if has_git:
                repos.append(dirpath)
                dirnames[:] = []  # 不再往下钻，避免子模块重复
    return unique_paths(repos)


def unique_paths(repos):
    seen, out = set(), []
    for r in repos:
        key = os.path.normcase(os.path.realpath(r))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def git(repo, *args, timeout=120):
    try:
        p = subprocess.run(
            ["git", "-C", repo] + list(args),
            capture_output=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    if p.returncode != 0:
        return ""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return p.stdout.decode(enc)
        except UnicodeDecodeError:
            continue
    return p.stdout.decode("utf-8", "replace")


def collect_local(roots, since, until, max_depth, emails, include_merges):
    """返回 {date: count} 以及统计辅助信息。"""
    repos = find_repos(roots, max_depth)
    seen_sha = {}
    emails_lc = {e.lower() for e in emails if e}
    per_email = {}

    for repo in repos:
        fmt = "%H%x1f%ae%x1f%ad"
        args = ["log", "--all", "--date=short", f"--since={since}", f"--until={until}",
                f"--pretty=format:{fmt}"]
        if not include_merges:
            args.insert(1, "--no-merges")
        out = git(repo, *args)
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 3:
                continue
            sha, email, date = parts
            email_lc = email.lower()
            per_email[email_lc] = per_email.get(email_lc, 0) + 1
            if emails_lc and email_lc not in emails_lc:
                continue
            if sha in seen_sha:          # 跨仓库去重
                continue
            seen_sha[sha] = date

    counts = {}
    for date in seen_sha.values():
        counts[date] = counts.get(date, 0) + 1
    return counts, per_email, len(repos)


# ---------------------------------------------------------------- GitHub 数据源

GQL = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""

GQL_COMMITS = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner isPrivate }
        contributions(first: 100) {
          nodes { occurredAt commitCount }
          pageInfo { hasNextPage }
        }
      }
    }
  }
}
"""


def _gql(token, query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://aPI.github.com/graphql", data=payload,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "heatmap-svg"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("errors"):
        raise SystemExit("GraphQL 错误: " + json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


def collect_github(login, token, start, end, commits_only=False):
    """calendar = 日历总数（commit+issue+PR+review+repo）；commits_only = 只数 commit。"""
    if commits_only:
        return _commit_counts(login, token, start, end, 0)

    d = _gql(token, GQL, {"login": login,
                          "from": start.isoformat() + "T00:00:00Z",
                          "to": end.isoformat() + "T23:59:59Z"})
    cal = d["user"]["contributionsCollection"]["contributionCalendar"]
    counts = {}
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            counts[day["date"]] = day["contributionCount"]
    return counts, cal["totalContributions"]


def _commit_counts(login, token, a, b, depth):
    """按时间窗取"只含 commit"的逐日计数；某仓库活跃天 ≥100 时对半拆窗重取。"""
    if b < a:
        return {}, 0
    d = _gql(token, GQL_COMMITS, {"login": login,
                                  "from": a.isoformat() + "T00:00:00Z",
                                  "to": b.isoformat() + "T23:59:59Z"})
    coll = d["user"]["contributionsCollection"]
    counts, overflow = {}, False
    for rp in coll["commitContributionsByRepository"]:
        conn = rp["contributions"]
        if conn["pageInfo"]["hasNextPage"] or len(conn["nodes"]) >= 100:
            overflow = True
        for n in conn["nodes"]:
            day = n["occurredAt"][:10]
            counts[day] = counts.get(day, 0) + n["commitCount"]

    if overflow and depth < 3 and a < b:
        mid = a + (b - a) // 2
        left, _ = _commit_counts(login, token, a, mid, depth + 1)
        right, _ = _commit_counts(login, token, mid + dt.timedelta(days=1), b, depth + 1)
        for day, v in right.items():
            left[day] = left.get(day, 0) + v
        return left, sum(left.values())
    return counts, sum(counts.values())


def resolve_token(explicit=None, gh="auto"):
    """按顺序拿 token：显式传入 → GH_TOKEN/GITHUB_TOKEN → gh CLI（本机或 WSL）。

    这是"官方路径"：你只要 `gh auth login` 登录过一次，脚本自己就去 gh 里取 token，
    不用手动复制、也不用配 secret。Windows 上没有 gh 时自动借 WSL 里的 gh。
    """
    if explicit:
        return explicit
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        val = os.environ.get(name, "").strip()
        if val:
            return val
    if gh == "off":
        return ""
    cmds = []
    if gh in ("auto", "native"):
        cmds.append(["gh", "auth", "token"])
    if gh in ("auto", "wsl") and os.name == "nt":
        cmds.append(["wsl.exe", "-e", "bash", "-lc", "gh auth token"])
    for cmd in cmds:
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            continue
        if out:
            return out
    return ""


def guess_login(cwd):
    url = git(cwd, "remote", "get-url", "origin")
    url = url.strip()
    if not url:
        return None
    for sep in ("github.com:", "github.com/"):
        if sep in url:
            tail = url.split(sep, 1)[1]
            return tail.split("/")[0] or None
    return None


# ---------------------------------------------------------------- 渲染

PALETTES = {
    "light": {"empty": "#ebedf0", "levels": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
              "text": "#57606a", "bg": "none", "border": "#d0d7de"},
    "dark": {"empty": "#161b22", "levels": ["#0e4429", "#006d32", "#26a641", "#39d353"],
             "text": "#8b949e", "bg": "none", "border": "#30363d"},
}

CELL, GAP = 10, 3


def blend(hex_color, other, t):
    """把 hex_color 往 other 混合 t(0..1)。"""
    a = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def palette(theme, accent):
    pal = dict(PALETTES[theme])
    if accent:
        base = accent if accent.startswith("#") else "#" + accent
        if theme == "light":
            pal["levels"] = [blend(base, "#ffffff", 0.72),
                             blend(base, "#ffffff", 0.46),
                             blend(base, "#ffffff", 0.20), base]
        else:
            pal["levels"] = [blend(base, "#0d1117", 0.72),
                             blend(base, "#0d1117", 0.46),
                             blend(base, "#0d1117", 0.20), base]
    return pal
STEP = CELL + GAP
LEFT, TOP = 30, 20
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_ZH = ["1月", "2月", "3月", "4月", "5月", "6月",
             "7月", "8月", "9月", "10月", "11月", "12月"]
WEEKDAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}
WEEKDAY_LABELS_ZH = {1: "一", 3: "三", 5: "五"}


def thresholds(counts):
    vals = sorted(v for v in counts.values() if v > 0)
    if not vals:
        return []
    n = len(vals)
    return [vals[min(n - 1, int(n * q))] for q in (0.25, 0.5, 0.75)]


def level_of(v, th):
    if v <= 0:
        return 0
    lv = 1
    for t in th:
        if v >= t:
            lv += 1
    return min(4, lv)


def build_grid(counts, start, end):
    """返回 weeks：list[list[(date|None, count)]]，列=周，行=星期(0=周日)。"""
    # 回退到周日
    first = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    weeks, cur = [], []
    d = first
    while d <= end:
        cur.append((d, counts.get(d.isoformat(), 0)))
        if len(cur) == 7:
            weeks.append(cur)
            cur = []
        d += dt.timedelta(days=1)
    if cur:
        cur += [(None, 0)] * (7 - len(cur))
        weeks.append(cur)
    return weeks


def render(counts, start, end, theme, lang, title_text,
           style="square", accent=None, animate=False):
    pal = palette(theme, accent)
    rx = CELL // 2 if style == "dot" else 2
    if style == "flat":
        rx = 0
    th = thresholds(counts)
    weeks = build_grid(counts, start, end)
    today = dt.date.today()
    grid_w = len(weeks) * STEP
    grid_h = 7 * STEP - GAP
    legend_w = 4 * STEP + 46
    foot = 26
    show_legend = (LEFT + grid_w + 8) >= legend_w + 56
    width = max(LEFT + grid_w + 8, 150)
    height = TOP + grid_h + foot

    total = sum(counts.values())
    active = sum(1 for v in counts.values() if v > 0)

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
      f'viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,'
      f'Segoe UI,Noto Sans,Helvetica,Arial,sans-serif">')
    a(f'<title>{title_text}</title>')
    if animate:
        a('<style>'
          '@keyframes hm-pop{0%{opacity:0;transform:scale(.35)}'
          '18%{opacity:1;transform:scale(1.06)}28%{transform:scale(1)}'
          '100%{opacity:1;transform:scale(1)}}'
          '@keyframes hm-breathe{0%,100%{opacity:1}50%{opacity:.55}}'
          '.hm-c{transform-box:fill-box;transform-origin:50% 50%;'
          'animation:hm-pop 1.2s cubic-bezier(.2,.7,.3,1) infinite}'
          '.hm-b{animation:hm-breathe 3.6s ease-in-out infinite}'
          '@media (prefers-reduced-motion: reduce){.hm-c,.hm-b{animation:none}}'
          '</style>')
    if pal["bg"] != "none":
        a(f'<rect width="{width}" height="{height}" fill="{pal["bg"]}"/>')

    # 月份标签（只看窗口内真正的第一天，避免把上一年的 12 月标出来）
    seen_month = None
    last_label_wi = -9
    for wi, week in enumerate(weeks):
        inside = [d for d, _ in week if d is not None and start <= d <= end]
        if not inside:
            continue
        m = inside[0].month
        if m == seen_month:
            continue
        seen_month = m
        if wi < len(weeks) - 1 and wi - last_label_wi >= 3:
            last_label_wi = wi
            label = (MONTHS_ZH if lang == "zh" else MONTHS)[m - 1]
            a(f'<text x="{LEFT + wi * STEP}" y="{TOP - 7}" fill="{pal["text"]}" '
              f'font-size="9.5">{label}</text>')

    # 星期标签
    for row, label in (WEEKDAY_LABELS_ZH if lang == "zh" else WEEKDAY_LABELS).items():
        a(f'<text x="0" y="{TOP + row * STEP + CELL - 1.5}" fill="{pal["text"]}" '
          f'font-size="9.5">{label}</text>')

    # 格子
    for wi, week in enumerate(weeks):
        for row, (d, v) in enumerate(week):
            if d is None:
                continue
            x = LEFT + wi * STEP
            y = TOP + row * STEP
            if d > today:
                continue
            lv = level_of(v, th)
            fill = pal["empty"] if lv == 0 else pal["levels"][lv - 1]
            if lang == "zh":
                tip = f"{d.isoformat()} · {v} 次提交"
            else:
                tip = f"{d.isoformat()} · {v} commit" + ("" if v == 1 else "s")
            cls = ""
            extra = ""
            if animate and v > 0:
                cls = ' class="hm-c' + (' hm-b' if lv >= 3 else '') + '"'
                extra = f' style="animation-delay:{(wi * 62 + row * 9) % 3400}ms"'
            a(f'<rect{cls}{extra} x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
              f'rx="{rx}" ry="{rx}" fill="{fill}"><title>{tip}</title></rect>')

    # 图例 + 汇总（只有聚合数字）；窄图（单月）放不下图例就只留汇总
    ly = TOP + grid_h + 14
    if show_legend:
        lx = width - legend_w
        a(f'<text x="{lx - 34}" y="{ly + 8}" fill="{pal["text"]}" font-size="9.5">'
          f'{"少" if lang == "zh" else "Less"}</text>')
        for i in range(5):
            fill = pal["empty"] if i == 0 else pal["levels"][i - 1]
            a(f'<rect x="{lx + i * STEP}" y="{ly}" width="{CELL}" height="{CELL}" rx="{rx}" ry="{rx}" '
              f'fill="{fill}"/>')
        a(f'<text x="{lx + 5 * STEP + 4}" y="{ly + 8}" fill="{pal["text"]}" font-size="9.5">'
          f'{"多" if lang == "zh" else "More"}</text>')

    if lang == "zh":
        summary = f"共 {total:,} 次提交 · {active} 天有提交"
    else:
        summary = f"{total:,} commits · {active} active days"
    a(f'<text x="0" y="{ly + 8}" fill="{pal["text"]}" font-size="9.5">{summary}</text>')

    a("</svg>")
    return "\n".join(out) + "\n", total, active


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="生成只含计数的贡献热力图 SVG")
    ap.add_argument("--source", choices=["local", "github"], default="local")
    ap.add_argument("--roots", nargs="+", default=["."], help="local 模式：要扫描的目录")
    ap.add_argument("--depth", type=int, default=3, help="local 模式：最大递归深度")
    ap.add_argument("--email", action="append", default=[],
                    help="local 模式：只统计这些作者邮箱（可多次；留空则全算）")
    ap.add_argument("--no-merges", dest="merges", action="store_false", default=True,
                    help="local 模式：排除 merge commit")
    ap.add_argument("--weeks", type=int, default=53, help="显示多少周（默认 53）")
    ap.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--out", default="assets", help="输出目录")
    ap.add_argument("--login", default=None, help="github 模式：用户名")
    ap.add_argument("--token-env", default="GH_TOKEN", help="github 模式：读 token 的环境变量名")
    ap.add_argument("--gh", default="auto", choices=["auto", "native", "wsl", "off"],
                    help="github 模式的 token 来源：auto/native 用本机 gh，wsl 用 WSL 里的 gh，off 只认环境变量")
    ap.add_argument("--commits-only", action="store_true",
                    help="github 模式：只数 commit，排除 issue / PR / review")
    ap.add_argument("--style", choices=["square", "dot", "flat"], default="square",
                    help="格子形状：square 圆角方块 / dot 圆点 / flat 直角方块")
    ap.add_argument("--accent", default=None,
                    help="主色，如 2f81f7 / #2f81f7；默认 GitHub 绿")
    ap.add_argument("--summary", action="store_true", help="只打印统计，不写文件")
    ap.add_argument("--force", action="store_true", help="github 模式取到 0 时也覆盖")
    ap.add_argument("--title", default=None, help="SVG <title> 文本（无障碍/悬浮提示）")
    args = ap.parse_args(argv)

    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    start = end - dt.timedelta(days=args.weeks * 7 - 1)

    if args.source == "local":
        emails = list(args.email)
        cfg = git(".", "config", "--get", "user.email").strip()
        if cfg and cfg not in emails:
            emails.append(cfg)
        if not cfg and not args.email:
            emails = []  # 拿不到就全算
        counts, per_email, nrepos = collect_local(
            args.roots, start.isoformat(), (end + dt.timedelta(days=1)).isoformat(),
            args.depth, emails, args.merges)
        print(f"[local] 扫描 {nrepos} 个仓库, {start} → {end}", file=sys.stderr)
        top = sorted(per_email.items(), key=lambda kv: -kv[1])[:6]
        if top:
            print("[local] 仓库里出现的作者邮箱（* = 计入）:", file=sys.stderr)
            for e, n in top:
                mark = "*" if e in {x.lower() for x in emails} else " "
                print(f"   {mark} {e}  {n}", file=sys.stderr)
        if not emails:
            print("[local] 警告: 未识别到作者邮箱，统计了所有作者（可能包含 clone 的上游提交）",
                  file=sys.stderr)
    else:
        login = args.login or guess_login(".")
        token = resolve_token(os.environ.get(args.token_env, ""), args.gh)
        if not login:
            raise SystemExit("github 模式需要 --login（或从 origin 自动识别失败）")
        if not token:
            raise SystemExit("github 模式取不到 token：先 `gh auth login`，或设置 %s" % args.token_env)
        counts, api_total = collect_github(login, token, start, end,
                                                    commits_only=args.commits_only)
        label = "提交合计" if args.commits_only else "日历总数"
        print(f"[github] {login}: {label} {api_total}", file=sys.stderr)
        if api_total == 0 and not args.force:
            print("[github] 注意: 你的公开贡献日历是 0（见 docs/heatmap.md 的体检清单）。"
                  "不覆盖已有 SVG，避免把好图冲成空白。", file=sys.stderr)
            if os.path.exists(os.path.join(args.out, "heatmap-light.svg")):
                return 0

    if args.summary:
        vals = sorted(counts.items())
        print(f"total={sum(counts.values())} active_days={sum(1 for _, v in vals if v)}")
        for d, v in vals[-14:]:
            print(f"  {d}  {v}")
        return 0

    os.makedirs(args.out, exist_ok=True)
    total_any = 0
    for theme in ("light", "dark"):
        title = args.title or "contribution heatmap"
        svg, total, active = render(counts, start, end, theme, args.lang, title,
                                    style=args.style, accent=args.accent)
        path = os.path.join(args.out, f"heatmap-{theme}.svg")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        total_any = total
        print(f"写入 {path}  ({total} commits / {active} days)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
