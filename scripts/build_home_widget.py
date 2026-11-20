#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建首页组件区：24 节气扇形盘 + 中华式时钟，并同步 CSP 的脚本哈希。"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import math
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "heatmap-data.json"
HOME = ROOT / "index.html"

WIDGET_RE = r'<!-- widget:begin -->.*?<!-- widget:end -->'
CSP_RE = r'<meta http-equiv="Content-Security-Policy" content="[^"]*">'
SCRIPT_RE = r'<script>.*?</script>'

# 从立春起，顺时针每 15° 一个节气
TERMS = [
    ("立春", 2, 4), ("雨水", 2, 19), ("惊蛰", 3, 5), ("春分", 3, 20),
    ("清明", 4, 4), ("谷雨", 4, 20), ("立夏", 5, 5), ("小满", 5, 21),
    ("芒种", 6, 5), ("夏至", 6, 21), ("小暑", 7, 7), ("大暑", 7, 22),
    ("立秋", 8, 7), ("处暑", 8, 23), ("白露", 9, 7), ("秋分", 9, 23),
    ("寒露", 10, 8), ("霜降", 10, 23), ("立冬", 11, 7), ("小雪", 11, 22),
    ("大雪", 12, 7), ("冬至", 12, 22), ("小寒", 1, 5), ("大寒", 1, 20),
]

CLOCK_JS = """(function(){
var T="子丑寅卯辰巳午未申酉戌亥",D="〇一二三四五六七八九";
var CD="初一初二初三初四初五初六初七初八初九初十十一十二十三十四十五十六十七十八十九二十廿一廿二廿三廿四廿五廿六廿七廿八廿九三十";
var p2=function(n){return String(n).padStart(2,"0")};
function cn(n){
  if(n<10)return D.charAt(n);
  if(n<20)return "十"+(n%10?D.charAt(n%10):"");
  return D.charAt(Math.floor(n/10))+"十"+(n%10?D.charAt(n%10):"");
}
function solar(d){
  var y=String(d.getFullYear()).replace(/[0-9]/g,function(c){return D.charAt(+c)});
  return y+"年"+cn(d.getMonth()+1)+"月"+cn(d.getDate())+"日";
}
var lf=null;
try{lf=new Intl.DateTimeFormat("zh-CN-u-ca-chinese",{year:"numeric",month:"long",day:"numeric"})}catch(e){}
var lk="",lv=null;
function lunar(d){
  if(!lf)return null;
  var k=d.toDateString();
  if(k===lk)return lv;
  lk=k;lv=null;
  try{
    var o={};
    lf.formatToParts(d).forEach(function(x){o[x.type]=x.value});
    var da=parseInt(o.day,10);
    if(o.yearName&&o.month&&da)lv=o.yearName+"年"+o.month+CD.substr((da-1)*2,2)+"日";
  }catch(e){}
  return lv;
}
// 百刻制：刻长 14.4 分，刻下十分，一时辰八刻，末 4.8 分为小刻
var ce=document.querySelector('[data-clock="cn"]'),ee=document.querySelector('[data-clock="ex"]');
function tick(){
  var d=new Date(),h=d.getHours(),mi=d.getMinutes(),s=d.getSeconds();
  var x=(h+1)%24,idx=Math.floor(x/2),off=(x%2)*60+mi+s/60+1e-9;
  var k=Math.floor(off/14.4),f=Math.floor((off-k*14.4)/1.44);
  var ck=off<115.2?"一二三四五六七八".charAt(k)+"刻"+(f?"一二三四五六七八九".charAt(f-1)+"分":""):"小刻";
  if(ce)ce.textContent=T.charAt(idx)+"时"+ck+"　"+(lunar(d)||solar(d));
  if(ee)ee.textContent=d.getFullYear()+"年"+(d.getMonth()+1)+"月"+d.getDate()+"日 "+p2(h)+":"+p2(mi)+":"+p2(s);
  if(ee)ee.textContent=d.getFullYear()+"年"+(d.getMonth()+1)+"月"+d.getDate()+"日 "+p2(h)+":"+p2(mi)+":"+p2(s);
}
tick();
setInterval(tick,1000);
})();"""


def bounds(year: int, i: int):
    m, d = TERMS[i][1], TERMS[i][2]
    s = dt.date(year, m, d)
    j = (i + 1) % 24
    e = dt.date(year, TERMS[j][1], TERMS[j][2])
    if e <= s:
        e = dt.date(year + 1, 1, 1)
    return s, e


def petal(r: float, a0: float, a1: float) -> str:
    x0, y0 = r * math.cos(a0), r * math.sin(a0)
    x1, y1 = r * math.cos(a1), r * math.sin(a1)
    return "M0 0L%.1f %.1fA%.1f %.1f 0 0 1 %.1f %.1fZ" % (x0, y0, r, r, x1, y1)


def apply_clock(text: str) -> str:
    digest = base64.b64encode(hashlib.sha256(CLOCK_JS.encode("utf-8")).digest()).decode("ascii")
    csp = ("default-src 'none'; script-src 'sha256-%s'; style-src 'unsafe-inline'; "
           "img-src 'self' data:; base-uri 'none'; form-action 'none'") % digest
    meta = '<meta http-equiv="Content-Security-Policy" content="%s">' % csp
    text, n = re.subn(CSP_RE, lambda m: meta, text, count=1)
    if n != 1:
        raise SystemExit("CSP meta 没找到")
    tag = "<script>%s</script>" % CLOCK_JS
    text, n = re.subn(SCRIPT_RE, lambda m: tag, text, count=1, flags=re.S)
    if n == 0:
        text = text.replace("</body>", tag + "\n</body>", 1)
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA), help="heatmap-data.json 路径")
    ap.add_argument("--home", default=str(HOME), help="首页 index.html 路径")
    args = ap.parse_args(argv)

    data_path = pathlib.Path(args.data)
    home_path = pathlib.Path(args.home)
    if not data_path.exists():
        raise SystemExit("缺数据文件：%s" % data_path)

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    years = payload.get("years") or {}
    if not years:
        raise SystemExit("数据文件里没有任何年份")

    filled = [int(k) for k, v in years.items() if v]
    year = max(filled) if filled else max(int(k) for k in years)
    raw = years.get(str(year)) or {}
    days = {}
    for k, v in raw.items():
        try:
            days[dt.date.fromisoformat(k)] = int(v)
        except ValueError:
            continue

    counts = []
    for i in range(24):
        s, e = bounds(year, i)
        counts.append(sum(v for d, v in days.items() if s <= d < e))
    mx = max(counts) or 1

    gap = math.radians(1.2)
    petals = []
    for i, c in enumerate(counts):
        a0 = math.radians(-90 + i * 15) + gap
        a1 = math.radians(-90 + (i + 1) * 15) - gap
        r = 38 + 70 * (c / mx) ** 0.6
        o = 0.30 + 0.62 * (c / mx)
        petals.append('<path d="%s" fill-opacity="%.2f"><title>%s · %d 次</title></path>'
                      % (petal(r, a0, a1), o, TERMS[i][0], c))

    total = sum(days.values())
    active = sum(1 for v in days.values() if v)
    label = "%d 年 24 节气提交分布，共 %d 次、%d 天有提交" % (year, total, active)

    block = """<!-- widget:begin -->
<section class="widgets" aria-label="组件">
  <article class="widget">
    <div class="widget-head">
      <span>当年活动(commit)</span>
      <a href="/heatmap/" title="展开看立体图" aria-label="展开立体热力图">→</a>
    </div>
    <div class="plate" role="img" aria-label="%s">
      <svg viewBox="-120 -120 240 240" aria-hidden="true">%s<circle class="hole" r="22"/></svg>
      <p class="marks"><b>立春</b><b>立夏</b><b>立秋</b><b>立冬</b></p>
    </div>
    <p class="plate-cap"><b>%d 次</b><span>%d 天有提交</span></p>
  </article>
  <article class="widget">
    <div class="widget-head">
      <span>此刻</span>
    </div>
    <div class="clock">
      <p class="clock-cn" data-clock="cn">—</p>
      <p class="clock-ex" data-clock="ex">—</p>
    </div>
    <p class="clock-note">*此计时采用隋至明制，一天十二时，一日百刻，一刻十分。</p>
  </article>
</section>
<!-- widget:end -->""" % (label, "".join(petals), total, active)

    text = home_path.read_text(encoding="utf-8")
    text, n = re.subn(WIDGET_RE, lambda m: block, text, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("首页标记没对上：widget=%d" % n)
    text = apply_clock(text)
    home_path.write_text(text, encoding="utf-8", newline="\n")
    print("组件区：%d 年 %d 次，24 段峰值 %d；时钟哈希已写入 CSP" % (year, total, mx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
