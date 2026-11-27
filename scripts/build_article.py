#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 content/writings/*.html 生成文章页：/writings/<file>/index.html。

正文片段只写正文，页头、页脚、目录、样式由本脚本补齐。
条目在 data/writings.json 的 items 里登记，带 file 字段的才会生成页面。

用法：
  python scripts/build_article.py            # 全量
  python scripts/build_article.py riscv32i   # 只生成一篇
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

from build_pages import BASE_CSS, ROOT, SHELL, esc

DATA = ROOT / "data" / "writings.json"
CONTENT = ROOT / "content" / "writings"

ARTICLE_CSS = """  .art-meta{
    margin:14px 0 0;
    color:var(--muted);
    font-size:.84rem;
    letter-spacing:.06em;
    font-variant-numeric:tabular-nums;
  }
  .art-layout{
    display:grid;
    grid-template-columns:196px minmax(0, 1fr);
    gap:0 52px;
    margin:34px 0 0;
  }
  .art-toc-wrap{ min-width:0 }
  .art-main{ min-width:0 }
  .art-toc{
    position:sticky;
    top:26px;
    max-height:calc(100vh - 52px);
    overflow-y:auto;
    overscroll-behavior:contain;
    padding:14px 4px 6px 0;
    border-top:1px solid var(--rule);
  }
  .art-toc-title{
    margin:0 0 12px;
    font-size:.72rem;
    color:var(--muted);
    letter-spacing:.22em;
  }
  .art-toc-list{
    margin:0;
    padding:0;
    list-style:none;
    font-size:.82rem;
    line-height:1.8;
  }
  .art-toc-list > li{ margin:0 0 .3em }
  .art-toc a{ color:var(--muted); text-decoration:none }
  .art-toc a:hover{ color:var(--ink) }
  .art-toc-sub{
    margin:.15em 0 .4em;
    padding:0;
    list-style:none;
    font-size:.77rem;
    line-height:1.7;
  }
  .art-toc-sub li{ padding-left:.9em; text-indent:-.9em }
  .article{
    max-width:none;
    margin:0;
    --fg:var(--ink);
    --fg-muted:var(--muted);
    --fg-faint:var(--muted);
    --bg-alt:var(--line);
    --accent:#a4402f;
  }
  @media (prefers-color-scheme: dark){
    .article{ --accent:#c9765f }
  }
  .article p{ margin:0 0 1.35em; line-height:1.95 }
  .article h2{
    margin:2.4em 0 .8em;
    font-size:clamp(1.2rem,1rem + .6vw,1.38rem);
    font-weight:400;
    letter-spacing:.03em;
    line-height:1.5;
  }
  .article h3{
    margin:1.9em 0 .55em;
    font-size:1.04rem;
    font-weight:400;
    letter-spacing:.03em;
  }
  .article ol, .article ul{ margin:0 0 1.4em; padding-left:1.5em }
  .article li{ margin:.3em 0; line-height:1.9 }
  .article a{
    color:inherit;
    text-decoration:none;
    border-bottom:1px solid var(--rule);
  }
  .article a:hover{ border-bottom-color:var(--ink) }
  .article figure{ margin:1.9em 0; text-align:center }
  .article figure svg{
    display:block;
    width:100%;
    max-width:720px;
    height:auto;
    margin:0 auto;
  }
  .article img{
    display:block;
    max-width:min(100%, 720px);
    height:auto;
    margin:0 auto;
    border:1px solid var(--line);
  }
  .article figcaption{
    max-width:720px;
    margin:.72em auto 0;
    text-align:left;
    color:var(--muted);
    font-size:.8rem;
    line-height:1.7;
  }
  .fig-no{ letter-spacing:.1em }
  .article pre{
    margin:1.5em 0;
    padding:14px 16px;
    border:1px solid var(--line);
    overflow-x:auto;
    font-size:.82rem;
    line-height:1.72;
  }
  .article code{
    font-family:ui-monospace,"Cascadia Code","JetBrains Mono",Consolas,monospace;
    font-size:.9em;
  }
  .article :not(pre) > code{
    padding:1px 5px;
    border:1px solid var(--line);
    border-radius:2px;
  }
  .table-wrap{ margin:1.6em 0; overflow-x:auto }
  .article table{
    width:100%;
    border-collapse:collapse;
    font-size:.84rem;
    line-height:1.7;
  }
  .article th, .article td{
    padding:8px 10px;
    border-bottom:1px solid var(--line);
    text-align:left;
    vertical-align:top;
  }
  .article th{
    font-weight:400;
    color:var(--muted);
    letter-spacing:.08em;
    white-space:nowrap;
  }
  .article blockquote{
    margin:1.6em 0;
    padding:2px 0 2px 14px;
    border-left:2px solid var(--rule);
    color:var(--muted);
    font-size:.9rem;
    line-height:1.85;
  }
  .article blockquote p{ margin:0 }
  .article .article-note{
    margin:0 0 1.8em;
    padding-left:12px;
    border-left:2px solid var(--rule);
    color:var(--muted);
    font-size:.86rem;
    line-height:1.8;
  }
  .art-back{
    margin:40px 0 0;
    padding-top:18px;
    border-top:1px solid var(--rule);
    font-size:.84rem;
    letter-spacing:.06em;
  }
  .art-back a{ color:var(--muted); text-decoration:none }
  .art-back a:hover{ color:var(--ink) }
  @media (max-width:900px){
    .art-layout{ grid-template-columns:1fr; gap:0 }
    .art-toc{
      position:static;
      max-height:34vh;
      margin:0 0 26px;
    }
    .article{ max-width:none }
  }
"""


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def build_toc(inner: str) -> str:
    entries = []
    cur = None
    for m in re.finditer(r'<h([23])\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</h\1>', inner, re.S):
        level, hid, text = m.group(1), m.group(2), plain(m.group(3))
        if level == "2" or cur is None:
            cur = {"id": hid, "text": text, "sub": []}
            entries.append(cur)
        else:
            cur["sub"].append({"id": hid, "text": text})
    if not entries:
        return ""
    out = ['      <nav class="art-toc" aria-label="文章目录">',
           '        <p class="art-toc-title">目录</p>',
           '        <ul class="art-toc-list">']
    for entry in entries:
        sub = ""
        if entry["sub"]:
            sub = '\n          <ul class="art-toc-sub">' + "".join(
                '\n            <li><a href="#%s">%s</a></li>' % (esc(s["id"]), esc(s["text"]))
                for s in entry["sub"]
            ) + '\n          </ul>\n        '
        out.append('        <li><a href="#%s">%s</a>%s</li>' % (esc(entry["id"]), esc(entry["text"]), sub))
    out.append('        </ul>')
    out.append('      </nav>')
    return "\n".join(out)


def wordcount(inner: str) -> int:
    text = plain(inner)
    return len(re.findall(r"[\u4e00-\u9fff]", text)) + len(re.findall(r"[A-Za-z0-9_]+", text))


def build(item: dict, meta: dict) -> pathlib.Path:
    name = item["file"]
    src = CONTENT / ("%s.html" % name)
    if not src.exists():
        raise SystemExit("缺正文片段：%s" % src)
    inner = src.read_text(encoding="utf-8")

    date = item.get("date", "")
    parts = date.split("-")
    shown = "%s 年 %d 月 %d 日" % (parts[0], int(parts[1]), int(parts[2])) if len(parts) == 3 else date
    words = wordcount(inner)
    meta_line = " · ".join(x for x in (shown, "约 %d 字" % words) if x)
    if item.get("tag"):
        meta_line += " · " + item["tag"]

    toc = build_toc(inner)
    body = "\n".join([
        '    <header class="head">',
        '      <p class="eyebrow">%s · %s</p>' % (esc(meta["index"]), esc(meta["latin"])),
        '      <h1 class="title">%s</h1>' % esc(item["title"]),
        '      <p class="art-meta">%s</p>' % esc(meta_line),
        '    </header>',
        '    <div class="art-layout">',
        '      <aside class="art-toc-wrap">',
        toc or '        <p class="art-toc-title">目录</p>',
        '      </aside>',
        '      <div class="art-main">',
        '        <article class="article">',
        inner.strip(),
        '        </article>',
        '        <p class="art-back"><a href="/writings/">← 文稿</a></p>',
        '      </div>',
        '    </div>',
    ])

    doc = (SHELL
           .replace("__TITLE__", "%s · B . H . C" % esc(item["title"]))
           .replace("__DESC__", esc(item.get("summary") or item["title"]))
           .replace("__MARK__", "— B . H . C —")
           .replace("__SINCE__", "since 2020.")
           .replace("__COPY__", "© 2026")
           .replace("__CSS__", BASE_CSS + ARTICLE_CSS)
           .replace("__BODY__", body)
           .replace('<a href="/">← 首页</a>', '<a href="/writings/">← 文稿</a>'))

    out = ROOT / "writings" / name / "index.html"
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
    meta = json.loads(DATA.read_text(encoding="utf-8"))
    items = [it for g in meta.get("groups", []) for it in g.get("items", []) if it.get("file")]
    if argv:
        items = [it for it in items if it["file"] in argv]
        if not items:
            raise SystemExit("没有匹配的文章：%s" % ", ".join(argv))

    for item in items:
        out = build(item, meta)
        print("生成 %-28s <- content/writings/%s.html" % (out.relative_to(ROOT).as_posix(), item["file"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
