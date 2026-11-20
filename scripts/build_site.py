#!/usr/bin/env python3
"""生成年度热力图页面（单文件 HTML，数据内联），支持增量更新。

首次：`--since` 到今年逐年查一遍。
之后：读 `--json-in` 里上次的 `generated`，只补「前一日 → 今天」，
      区间外的旧数据原样保留；一个月没开电脑也只补一个月。
空年份保留成空对象，年份按钮照常能切，切过去是空图。

只取「commit 次数」：不请求仓库名、issue/PR 标题、提交信息。
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent


def load_heatmap():
    spec = importlib.util.spec_from_file_location("heatmap", HERE / "heatmap.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_prev(path):
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def parse_generated(payload):
    raw = payload.get("generated")
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def collect_range(hm, login, token, start, end):
    """按自然年切片查询，返回 {年份(int): {"YYYY-MM-DD": 次数}}。"""
    got = {}
    y = start.year
    while y <= end.year:
        s = max(start, dt.date(y, 1, 1))
        e = min(end, dt.date(y, 12, 31))
        if s <= e:
            counts, _ = hm.collect_github(login, token, s, e, commits_only=True)
            got[y] = {d: v for d, v in counts.items() if v > 0}
            print(f"[{y}] {s} -> {e}: {sum(got[y].values())} commits / {len(got[y])} days",
                  file=sys.stderr)
        y += 1
    return got


def merge(old_years, got, start, end):
    """用新数据覆盖 start..end 每一天，区间外的旧值不动。"""
    data = {str(k): dict(v) for k, v in old_years.items()}
    d = start
    while d <= end:
        key = d.isoformat()
        y = str(d.year)
        v = got.get(d.year, {}).get(key, 0)
        if v:
            data.setdefault(y, {})[key] = v
        elif y in data:
            data[y].pop(key, None)
        d += dt.timedelta(days=1)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", required=True)
    ap.add_argument("--token-env", default="GH_TOKEN")
    ap.add_argument("--gh", default="auto", choices=["auto", "native", "wsl", "off"])
    ap.add_argument("--since", type=int, default=2015,
                    help="首次全量的起点年份（含），默认 2015")
    ap.add_argument("--years", nargs="+", type=int, default=None,
                    help="只重查指定年份（不增量），其余年份原样保留")
    ap.add_argument("--full", action="store_true",
                    help="忽略旧数据，从 --since 全量重查")
    ap.add_argument("--drop-empty", action="store_true",
                    help="删掉完全没有提交的年份（默认保留成空年）")
    ap.add_argument("--out", default=str(ROOT / "heatmap" / "index.html"))
    ap.add_argument("--template", default=str(HERE / "site_template.html"))
    ap.add_argument("--json-out", default=None, help="另外存一份纯数据 JSON")
    ap.add_argument("--json-in", default=None, help="读旧数据做增量；默认与 --json-out 同路径")
    args = ap.parse_args(argv)

    hm = load_heatmap()
    token = hm.resolve_token(os.environ.get(args.token_env, ""), args.gh)
    if not token:
        raise SystemExit("取不到 token：先 `gh auth login`，或设置 %s（gh auth token）" % args.token_env)

    today = dt.date.today()
    json_out = args.json_out or str(ROOT / "heatmap-data.json")
    prev = {} if args.full else load_prev(args.json_in or json_out)
    old_years = prev.get("years") or {}
    last = parse_generated(prev) if prev else None

    if args.years:
        targets = sorted(set(args.years))
        got = {}
        for y in targets:
            s, e = dt.date(y, 1, 1), min(dt.date(y, 12, 31), today)
            if s <= e:
                got.update(collect_range(hm, args.login, token, s, e))
        data = {str(k): dict(v) for k, v in old_years.items()}
        for y in targets:
            data[str(y)] = got.get(y, {})
        print(f"重查 {len(targets)} 个年份", file=sys.stderr)
    elif last and not args.full:
        start = max(last - dt.timedelta(days=1), dt.date(args.since, 1, 1))
        if start > today:
            start = today
        got = collect_range(hm, args.login, token, start, today)
        data = merge(old_years, got, start, today)
        print(f"增量：{start} -> {today}（上次 {last}）", file=sys.stderr)
    else:
        data = collect_range(hm, args.login, token, dt.date(args.since, 1, 1), today)
        data = {str(y): data.get(y, {}) for y in range(args.since, today.year + 1)}
        print(f"全量：{args.since} -> {today.year}", file=sys.stderr)

    for y in range(args.since, today.year + 1):
        data.setdefault(str(y), {})
    if args.drop_empty:
        data = {k: v for k, v in data.items() if v}
    ordered = {k: data[k] for k in sorted(data, key=lambda s: int(s))}

    payload = {
        "login": args.login,
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "years": ordered,
    }

    tpl = pathlib.Path(args.template).read_text(encoding="utf-8")
    html = (tpl
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            .replace("__LOGIN__", args.login)
            .replace("__GENERATED__", payload["generated"]))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8", newline="\n")
    print(f"写入 {out} ({len(html) / 1024:.1f} KB)", file=sys.stderr)

    pathlib.Path(json_out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n")
    print(f"写入 {json_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
