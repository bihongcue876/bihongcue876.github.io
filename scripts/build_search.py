#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成站内检索：search.json 索引 + /search/ 页面。

索引覆盖五个分区的条目与文章正文；页面是无依赖的静态页，
由 /assets/search.js 读索引并在本机匹配，不发外部请求。

用法：
  python scripts/build_search.py
"""
from __future__ import annotations

import json
import re
import pathlib
import sys

from build_pages import BASE_CSS, DATA, ROOT, SHELL, esc


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


OUT_INDEX = ROOT / "search.json"
OUT_PAGE = ROOT / "search" / "index.html"

# 没有条目登记、但值得被搜到的页面
PAGES = [
    ("首页", "/"),
    ("黄历", "/calendar/"),
    ("年度提交热力图", "/heatmap/"),
]

CSP = ("default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
       "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'")

SEARCH_CSS = """  .search{ margin:34px 0 0 }
  .search input{
    width:100%;
    padding:13px 2px;
    border:0;
    border-bottom:1px solid var(--rule);
    background:transparent;
    color:var(--ink);
    font:inherit;
    font-size:1.05rem;
    letter-spacing:.02em;
  }
  .search input::placeholder{ color:var(--muted); opacity:.7 }
  .search input:focus{ outline:none; border-bottom-color:var(--ink) }
  .search-meta{
    margin:16px 0 0;
    color:var(--muted);
    font-size:.8rem;
    letter-spacing:.08em;
    font-variant-numeric:tabular-nums;
  }
  .search-list{ margin:8px 0 0; padding:0; list-style:none }
  .search-list li{ padding:16px 2px; border-bottom:1px solid var(--line) }
  .search-list a{
    display:flex;
    justify-content:space-between;
    align-items:baseline;
    gap:16px;
    color:inherit;
    text-decoration:none;
  }
  .search-list a:hover .s-title{ text-decoration:underline; text-underline-offset:.3em }
  .s-title{ font-size:1.02rem; letter-spacing:.03em }
  .s-kind{
    color:var(--muted);
    font-size:.74rem;
    letter-spacing:.14em;
    white-space:nowrap;
  }
  .s-frag{
    display:block;
    margin-top:7px;
    color:var(--muted);
    font-size:.85rem;
    line-height:1.75;
  }
  .s-frag mark{ background:transparent; color:var(--ink); font-weight:600 }
"""

BODY = """    <header class="head">
      <p class="eyebrow">00 · SEARCH</p>
      <h1 class="title">检索</h1>
      <p class="lede">输入关键词，标题、说明与正文一并查。索引在构建时生成，检索在本机完成。</p>
    </header>
    <form class="search" role="search" action="/search/" method="get">
      <input id="q" name="q" type="search" placeholder="键入关键词，如 RISC-V、指令、热力图" autocomplete="off" spellcheck="false">
    </form>
    <p class="search-meta" id="meta">正在载入索引…</p>
    <ul class="search-list" id="list"></ul>
    <script src="/assets/search.js"></script>"""


def text_of(html: str) -> str:
    raw = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    raw = re.sub(r"<svg\b.*?</svg>", " ", raw, flags=re.S | re.I)
    return plain(raw)


def collect() -> list:
    docs = []
    seen = {}

    def push(doc):
        url = doc["u"]
        if url in seen:
            prev = seen[url]
            if doc.get("x") and not prev.get("x"):
                prev["x"] = doc["x"]
            return
        seen[url] = doc
        docs.append(doc)

    for path in sorted(DATA.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        kind = data.get("title") or data.get("slug", "")
        page = "/%s/" % data.get("slug", "")
        ledger = {"t": kind, "u": page, "k": "分区"}
        if data.get("lede"):
            ledger["d"] = data["lede"]
        push(ledger)

        items = list(data.get("items") or [])
        for group in data.get("groups", []):
            items += group.get("items") or []
        for item in items:
            title = item.get("title") or item.get("name")
            if not title:
                continue
            url = item.get("href") or page
            note = item.get("note") or item.get("desc") or ""
            extra = ""
            name = item.get("file")
            if name:
                frag = ROOT / "content" / "writings" / ("%s.html" % name)
                if frag.exists():
                    extra = text_of(frag.read_text(encoding="utf-8"))
                    url = item.get("href") or ("/writings/%s/" % name)
            doc = {"t": title, "u": url, "k": kind}
            if note:
                doc["d"] = note
            if extra:
                doc["x"] = extra
            push(doc)

    for title, url in PAGES:
        push({"t": title, "u": url, "k": "页面"})
    return docs


def render(docs: list) -> str:
    body = BODY
    doc = (SHELL
           .replace("__TITLE__", "检索 · B . H . C")
           .replace("__DESC__", "站内检索：按关键词查标题、说明与正文。")
           .replace('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src \'self\' data:; base-uri \'none\'; form-action \'none\'">',
                    '<meta http-equiv="Content-Security-Policy" content="%s">' % CSP)
           .replace("__MARK__", "— B . H . C —")
           .replace("__SINCE__", "since 2020.")
           .replace("__COPY__", "© 2026")
           .replace("__CSS__", BASE_CSS + SEARCH_CSS)
           .replace("__BODY__", body)
           .replace('<a href="/">← 首页</a>', '<a href="/">← 首页</a>'))
    return doc


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    docs = collect()
    payload = json.dumps(docs, ensure_ascii=False, separators=(",", ":"))
    OUT_INDEX.write_text(payload, encoding="utf-8", newline="\n")
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(render(docs), encoding="utf-8", newline="\n")
    print("检索索引 %d 条，%.1f KB" % (len(docs), len(payload.encode("utf-8")) / 1024))
    print("生成 search/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
