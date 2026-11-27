#!/usr/bin/env python3
"""由 data/*.json 生成五个分区的静态页面。

约束：
  * 产物是纯静态 HTML，不含 <script>，不发外部请求；
  * 展示项全部由 data/ 下的 JSON 注册，改完 JSON 重跑本脚本即可；
  * 五个分区共用同一套页头、页脚、色板与字体栈，仅正文布局不同。

用法：
  python scripts/build_pages.py              # 全量生成
  python scripts/build_pages.py projects     # 只生成指定分区
"""
from __future__ import annotations

import html
import json
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SITE_MARK = "— B . H . C —"
SITE_SINCE = "since 2020."
SITE_COPY = "© 2026"

SHELL = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<style>
__CSS__
</style>
</head>
<body>
<div class="page">
  <header class="masthead">
    <p class="mark"><a href="/">__MARK__</a></p>
    <p class="since">__SINCE__</p>
  </header>

  <main>
__BODY__
  </main>

  <footer class="site-footer">
    <span>__COPY__</span>
    <span class="foot-links"><a href="/search/">检索</a> · <a href="/">← 首页</a></span>
  </footer>
</div>
</body>
</html>
"""

BASE_CSS = """  :root{
    --paper:#f8f5ef;
    --ink:#1d1b18;
    --muted:#6d665c;
    --line:#e4ddd1;
    --rule:#d2c9ba;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --paper:#141312;
      --ink:#e8e3d9;
      --muted:#9b9285;
      --line:#2a2723;
      --rule:#3a352d;
    }
  }
  *{ box-sizing:border-box }
  html{ -webkit-text-size-adjust:100% }
  body{
    margin:0;
    background:var(--paper);
    color:var(--ink);
    font-family:Georgia, "Times New Roman", "Iowan Old Style",
                "Songti SC", "Noto Serif SC", "Noto Serif CJK SC",
                "Source Han Serif SC", "SimSun", serif;
    font-size:16px;
    line-height:1.9;
    -webkit-font-smoothing:antialiased;
    text-rendering:optimizeLegibility;
  }
  ::selection{ background:var(--line) }
  .page{
    padding:clamp(32px,7vh,64px) clamp(20px,4vw,64px) 48px;
  }
  .masthead{
    display:flex;
    justify-content:space-between;
    align-items:baseline;
    gap:16px;
    padding-bottom:14px;
    border-bottom:1px solid var(--rule);
  }
  .mark{
    margin:0;
    font-size:.9rem;
    font-style:italic;
    letter-spacing:.18em;
  }
  .mark a{ color:inherit; text-decoration:none }
  .since{
    margin:0;
    font-size:.78rem;
    color:var(--muted);
    letter-spacing:.06em;
  }
  .head{
    margin:clamp(36px,6vh,56px) 0 0;
    padding-bottom:26px;
    border-bottom:1px solid var(--rule);
  }
  .eyebrow{
    margin:0;
    font-size:.74rem;
    color:var(--muted);
    letter-spacing:.24em;
  }
  .title{
    margin:14px 0 0;
    font-size:clamp(1.9rem, 1.15rem + 2.2vw, 2.9rem);
    font-weight:400;
    line-height:1.32;
    letter-spacing:.04em;
  }
  .lede{
    margin:14px 0 0;
    color:var(--muted);
    font-size:.95rem;
    line-height:1.85;
  }
  .group-label{
    margin:38px 0 0;
    font-size:.76rem;
    font-weight:400;
    color:var(--muted);
    letter-spacing:.22em;
  }
  .group-label::before{
    content:"";
    display:inline-block;
    width:1.3rem;
    height:1px;
    margin-right:10px;
    vertical-align:.3em;
    background:var(--rule);
  }
  .site-footer{
    margin:64px 0 0;
    display:flex;
    justify-content:space-between;
    align-items:baseline;
    color:var(--muted);
    font-size:.8rem;
    letter-spacing:.04em;
  }
  .site-footer a{
    color:var(--muted);
    text-decoration:none;
    padding-bottom:1px;
    border-bottom:1px solid var(--line);
  }
  .site-footer a:hover{ color:var(--ink); border-bottom-color:var(--ink) }
  a:focus-visible{ outline:1px solid var(--ink); outline-offset:2px }
  @media (prefers-reduced-motion: reduce){
    *{ transition:none !important }
  }
"""

CSS_INDEXED = """  .group-nav{ margin:26px 0 0 }
  .group-nav ul{
    margin:0;
    padding:0;
    list-style:none;
    display:flex;
    flex-wrap:wrap;
    gap:6px 20px;
    font-size:.8rem;
    letter-spacing:.08em;
  }
  .group-nav a{ color:var(--muted); text-decoration:none }
  .group-nav a:hover{ color:var(--ink) }
  .group-nav + .group .group-label{ margin-top:22px }
  .group-note{
    margin:12px 0 0;
    color:var(--muted);
    font-size:.87rem;
    line-height:1.8;
  }
  .group-note a{ color:var(--ink) }
  .entries{ margin:0; padding:0; list-style:none }
  .entry{ border-bottom:1px solid var(--line) }
  .entry-link{
    display:grid;
    grid-template-columns:2.4rem 1fr auto;
    gap:4px 18px;
    align-items:baseline;
    padding:18px 4px;
    color:inherit;
    text-decoration:none;
  }
  .entry-link:hover .entry-title{
    text-decoration:underline;
    text-underline-offset:.3em;
    text-decoration-thickness:1px;
  }
  .entry-link:hover .no{ color:var(--ink) }
  a.entry-link:focus-visible{ outline:1px solid var(--ink); outline-offset:-1px }
  .no{
    font-size:.78rem;
    color:var(--muted);
    font-variant-numeric:tabular-nums;
    letter-spacing:.08em;
  }
  .entry-main{ display:block }
  .entry-title{ display:block; font-size:1.08rem; letter-spacing:.03em }
  .entry-note{
    display:block;
    margin-top:6px;
    color:var(--muted);
    font-size:.86rem;
    line-height:1.72;
  }
  .entry-meta{
    display:flex;
    flex-direction:column;
    align-items:flex-end;
    gap:2px;
    font-size:.76rem;
    color:var(--muted);
    white-space:nowrap;
  }
  .entry-meta .status{ letter-spacing:.1em }
  .entry-meta .year{ font-variant-numeric:tabular-nums; letter-spacing:.04em }
  .entry-link.is-plain{ cursor:default }
  .entry-link.is-plain:hover .entry-title{ text-decoration:none }
  .entry-links{
    display:flex;
    flex-wrap:wrap;
    gap:6px 16px;
    margin:0;
    padding:0 4px 16px;
    font-size:.78rem;
    letter-spacing:.06em;
  }
  .entry-links a{
    color:var(--muted);
    text-decoration:none;
    padding-bottom:1px;
    border-bottom:1px solid var(--line);
  }
  .entry-links a:hover{ color:var(--ink); border-bottom-color:var(--ink) }
  .entry.is-empty .entry-note{ font-style:italic }
  @media (max-width:660px){
    .entry-link{ grid-template-columns:1.9rem 1fr }
    .entry-meta{
      grid-column:2;
      flex-direction:row;
      align-items:baseline;
      gap:14px;
      margin-top:8px;
    }
  }
"""

CSS_PLATES = """  .plates{ margin:34px 0 0 }
  .plate{
    margin:0 0 38px;
    padding:2px 0 2px 24px;
    border-left:1px solid var(--rule);
    transition:border-color .18s ease;
  }
  .plate:last-child{ margin-bottom:0 }
  .plate:hover{ border-left-color:var(--muted) }
  .plate-kicker{
    margin:0;
    font-size:.76rem;
    color:var(--muted);
    letter-spacing:.16em;
  }
  .plate-title{
    margin:8px 0 0;
    font-size:clamp(1.34rem, 1rem + 1.3vw, 1.95rem);
    font-weight:400;
    line-height:1.42;
    letter-spacing:.03em;
  }
  .plate-title a{ color:inherit; text-decoration:none }
  .plate-title a:hover{
    text-decoration:underline;
    text-underline-offset:.3em;
    text-decoration-thickness:1px;
  }
  .plate-desc{
    margin:10px 0 0;
    max-width:66ch;
    color:var(--muted);
    font-size:.92rem;
    line-height:1.85;
  }
"""

CSS_TOC = """  .group-note{
    margin:12px 0 0;
    color:var(--muted);
    font-size:.87rem;
    line-height:1.8;
  }
  .group-note a{ color:var(--ink) }
  .toc{ margin:0; padding:0; list-style:none }
  .toc-item{ padding:15px 2px; border-bottom:1px solid var(--line) }
  .toc-line{ display:flex; align-items:baseline; gap:12px; margin:0 }
  .toc-title{ font-size:1.02rem; letter-spacing:.03em }
  a.toc-title{ color:inherit; text-decoration:none }
  a.toc-title:hover{
    text-decoration:underline;
    text-underline-offset:.3em;
    text-decoration-thickness:1px;
  }
  .toc-dots{
    flex:1;
    min-width:1.5rem;
    border-bottom:1px dotted var(--rule);
    transform:translateY(-.3em);
  }
  .toc-date{
    color:var(--muted);
    font-size:.78rem;
    font-variant-numeric:tabular-nums;
    letter-spacing:.08em;
    white-space:nowrap;
  }
  .toc-note{
    margin:7px 0 0;
    color:var(--muted);
    font-size:.86rem;
    line-height:1.72;
  }
  .toc-tag{
    margin-left:11px;
    padding-left:11px;
    border-left:1px solid var(--rule);
    letter-spacing:.1em;
  }
  @media (max-width:560px){
    .toc-dots{ display:none }
    .toc-line{ gap:0 }
    .toc-date{ margin-left:auto; padding-left:12px }
  }
"""

CSS_LIST = """  .group-note{
    margin:12px 0 0;
    color:var(--muted);
    font-size:.87rem;
    line-height:1.8;
  }
  .items{
    margin:0;
    padding:0;
    list-style:none;
    display:grid;
    grid-template-columns:repeat(2, minmax(0, 1fr));
    gap:0 44px;
  }
  .item{ border-bottom:1px solid var(--line) }
  .item-inner{
    display:grid;
    grid-template-columns:1fr auto;
    align-items:baseline;
    gap:2px 12px;
    padding:12px 2px;
    color:inherit;
    text-decoration:none;
  }
  .item-name{ font-size:.95rem; letter-spacing:.03em }
  a.item-inner:hover .item-name{
    text-decoration:underline;
    text-underline-offset:.28em;
    text-decoration-thickness:1px;
  }
  .item-tag{
    color:var(--muted);
    font-size:.72rem;
    letter-spacing:.12em;
    font-variant-numeric:tabular-nums;
    white-space:nowrap;
  }
  .item-note{
    grid-column:1 / -1;
    color:var(--muted);
    font-size:.82rem;
    line-height:1.65;
  }
  @media (max-width:720px){
    .items{ grid-template-columns:1fr; gap:0 }
  }
"""

CSS_PROSE = """  .prose{ max-width:74ch; margin-top:34px }
  .prose p{ margin:0 0 1.5em; line-height:1.95 }
  .prose p:first-child{ font-size:1.03rem }
  .prose a{
    color:inherit;
    text-decoration:none;
    border-bottom:1px solid var(--line);
  }
  .prose a:hover{ border-bottom-color:var(--ink) }
  .facts{
    display:grid;
    grid-template-columns:max-content 1fr;
    gap:12px 30px;
    margin:44px 0 0;
    padding-top:22px;
    border-top:1px solid var(--rule);
  }
  .fact{ display:contents }
  .facts dt{
    color:var(--muted);
    font-size:.82rem;
    letter-spacing:.14em;
  }
  .facts dd{ margin:0; font-size:.94rem }
  @media (max-width:520px){
    .facts{ grid-template-columns:1fr; gap:0 }
    .facts dt{ margin-top:16px }
    .facts dd{ margin-bottom:2px }
  }
"""

LAYOUT_CSS = {
    "indexed": CSS_INDEXED,
    "plates": CSS_PLATES,
    "toc": CSS_TOC,
    "list": CSS_LIST,
    "prose": CSS_PROSE,
}

LINK_RE = r"\[([^\]\n]+)\]\(([^)\s]+)\)"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def rich(text) -> str:
    """转义后把 [文字](/路径/) 解成站内链接。"""
    raw = esc(text)
    return re.sub(LINK_RE, lambda m: '<a href="%s">%s</a>' % (m.group(2), m.group(1)), raw)


def wrap_link(cls: str, href, inner: str) -> str:
    if href:
        return '<a class="%s" href="%s" rel="noreferrer noopener">%s</a>' % (cls, esc(href), inner)
    return '<span class="%s is-plain">%s</span>' % (cls, inner)


def render_indexed(data: dict) -> str:
    groups = data.get("groups", [])
    out = []

    nav = []
    for group in groups:
        if not (group.get("label") and group.get("id")):
            continue
        nav.append('        <li><a href="#%s">%s</a></li>' % (esc(group["id"]), esc(group["label"])))
    if len(nav) > 1:
        out.append('    <nav class="group-nav" aria-label="分类">')
        out.append('      <ul>')
        out.extend(nav)
        out.append('      </ul>')
        out.append('    </nav>')

    for group in groups:
        gid = (' id="%s"' % esc(group["id"])) if group.get("id") else ""
        out.append('    <section class="group"%s>' % gid)
        if group.get("label"):
            out.append('      <h2 class="group-label">%s</h2>' % esc(group["label"]))
        if group.get("note"):
            out.append('      <p class="group-note">%s</p>' % rich(group["note"]))
        out.append('      <ol class="entries">')
        items = group.get("items") or []
        if not items and group.get("empty") is not False:
            out.append(
                '        <li class="entry is-empty"><span class="entry-link is-plain">'
                '<span class="no">—</span>'
                '<span class="entry-main"><span class="entry-note">%s</span></span>'
                '</span></li>' % esc(group.get("empty") or "暂无条目")
            )
        for i, item in enumerate(items, 1):
            href = item.get("href")
            meta = []
            if item.get("status"):
                meta.append('<span class="status">%s</span>' % esc(item["status"]))
            if item.get("year"):
                meta.append('<span class="year">%s</span>' % esc(item["year"]))
            note = ""
            if item.get("note"):
                text = esc(item["note"]) if href else rich(item["note"])
                note = '<span class="entry-note">%s</span>' % text
            inner = (
                '<span class="no">%s</span>'
                '<span class="entry-main">'
                '<span class="entry-title">%s</span>%s'
                '</span>'
                '%s'
            ) % (
                esc(item.get("no") or "%02d" % i),
                esc(item["title"]),
                note,
                ('<span class="entry-meta">%s</span>' % "".join(meta)) if meta else "",
            )
            links = item.get("links") or []
            extra = ""
            if links:
                extra = '\n          <p class="entry-links">%s</p>' % "".join(
                    '<a href="%s" rel="noreferrer noopener">%s</a>' % (esc(x["href"]), esc(x["label"]))
                    for x in links
                )
            out.append('        <li class="entry">%s%s</li>' % (wrap_link("entry-link", href, inner), extra))
        out.append('      </ol>')
        out.append('    </section>')
    return "\n".join(out)


def render_plates(data: dict) -> str:
    items = data.get("items") or []
    if not items:
        return ""
    out = ['    <section class="plates">']
    for item in items:
        title = esc(item["title"])
        if item.get("href"):
            title = '<a href="%s">%s</a>' % (esc(item["href"]), title)
        desc = ('\n        <p class="plate-desc">%s</p>' % esc(item["desc"])) if item.get("desc") else ""
        out.append(
            '      <article class="plate">\n'
            '        <p class="plate-kicker">%s</p>\n'
            '        <h2 class="plate-title">%s</h2>%s\n'
            '      </article>' % (esc(item.get("kicker", "")), title, desc)
        )
    out.append('    </section>')
    return "\n".join(out)


def render_toc(data: dict) -> str:
    out = []
    for group in data.get("groups", []):
        gid = (' id="%s"' % esc(group["id"])) if group.get("id") else ""
        out.append('    <section class="group"%s>' % gid)
        if group.get("label"):
            out.append('      <h2 class="group-label">%s</h2>' % esc(group["label"]))
        if group.get("note"):
            out.append('      <p class="group-note">%s</p>' % rich(group["note"]))
        out.append('      <ul class="toc">')
        items = group.get("items") or []
        if not items and group.get("empty") is not False:
            out.append('        <li class="toc-item"><p class="toc-note">%s</p></li>'
                       % esc(group.get("empty") or "暂无条目"))
        for item in items:
            if item.get("href"):
                title = '<a class="toc-title" href="%s">%s</a>' % (esc(item["href"]), esc(item["title"]))
            else:
                title = '<span class="toc-title">%s</span>' % esc(item["title"])
            note = ('\n          <p class="toc-note">%s</p>' % esc(item["note"])) if item.get("note") else ""
            right = esc(item.get("date", ""))
            if item.get("tag"):
                right = '%s<span class="toc-tag">%s</span>' % (right, esc(item["tag"]))
            out.append(
                '        <li class="toc-item">\n'
                '          <p class="toc-line">%s<span class="toc-dots"></span>'
                '<span class="toc-date">%s</span></p>%s\n'
                '        </li>' % (title, right, note)
            )
        out.append('      </ul>')
        out.append('    </section>')
    return "\n".join(out)


def render_list(data: dict) -> str:
    out = []
    for group in data.get("groups", []):
        gid = (' id="%s"' % esc(group["id"])) if group.get("id") else ""
        out.append('    <section class="group"%s>' % gid)
        if group.get("label"):
            out.append('      <h2 class="group-label">%s</h2>' % esc(group["label"]))
        if group.get("note"):
            out.append('      <p class="group-note">%s</p>' % rich(group["note"]))
        out.append('      <ul class="items">')
        items = group.get("items") or []
        if not items and group.get("empty") is not False:
            out.append('        <li class="item"><span class="item-inner is-plain">'
                       '<span class="item-note">%s</span></span></li>'
                       % esc(group.get("empty") or "暂无条目"))
        for item in items:
            note = ('<span class="item-note">%s</span>' % esc(item["note"])) if item.get("note") else ""
            tag = ('<span class="item-tag">%s</span>' % esc(item["tag"])) if item.get("tag") else ""
            inner = '<span class="item-name">%s</span>%s%s' % (esc(item["name"]), tag, note)
            out.append('        <li class="item">%s</li>' % wrap_link("item-inner", item.get("href"), inner))
        out.append('      </ul>')
        out.append('    </section>')
    return "\n".join(out)


def render_prose(data: dict) -> str:
    out = []
    if data.get("paragraphs"):
        out.append('    <article class="prose">')
        for text in data["paragraphs"]:
            out.append('      <p>%s</p>' % rich(text))
        out.append('    </article>')
    if data.get("facts"):
        out.append('    <dl class="facts">')
        for fact in data["facts"]:
            out.append(
                '      <div class="fact"><dt>%s</dt><dd>%s</dd></div>'
                % (esc(fact["k"]), rich(fact["v"]))
            )
        out.append('    </dl>')
    return "\n".join(out)


LAYOUTS = {
    "indexed": render_indexed,
    "plates": render_plates,
    "toc": render_toc,
    "list": render_list,
    "prose": render_prose,
}


def build(path: pathlib.Path) -> pathlib.Path:
    data = json.loads(path.read_text(encoding="utf-8"))
    layout = data["layout"]
    if layout not in LAYOUTS:
        raise SystemExit("%s: 未知 layout %r（可用：%s）" % (path.name, layout, ", ".join(LAYOUTS)))

    head = [
        '    <header class="head">',
        '      <p class="eyebrow">%s · %s</p>' % (esc(data["index"]), esc(data["latin"])),
        '      <h1 class="title">%s</h1>' % esc(data["title"]),
    ]
    if data.get("lede"):
        head.append('      <p class="lede">%s</p>' % esc(data["lede"]))
    head.append('    </header>')
    head = "\n".join(head)

    body = head + "\n" + LAYOUTS[layout](data)
    css = BASE_CSS + LAYOUT_CSS[layout]

    doc = (SHELL
           .replace("__TITLE__", "%s · B . H . C" % esc(data["title"]))
           .replace("__DESC__", esc(data.get("lede") or data["title"]))
           .replace("__MARK__", SITE_MARK)
           .replace("__SINCE__", SITE_SINCE)
           .replace("__COPY__", SITE_COPY)
           .replace("__CSS__", css)
           .replace("__BODY__", body))

    out = ROOT / data["slug"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8", newline="\n")
    return out


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    argv = list(sys.argv[1:] if argv is None else argv)
    files = sorted(DATA.glob("*.json"))
    if argv:
        files = [f for f in files if f.stem in argv]
        if not files:
            raise SystemExit("没有匹配的 JSON：%s" % ", ".join(argv))

    for path in files:
        out = build(path)
        print("生成 %-24s <- data/%s" % (out.relative_to(ROOT).as_posix(), path.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
