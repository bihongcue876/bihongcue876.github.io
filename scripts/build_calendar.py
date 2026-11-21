#!/usr/bin/env python3
"""生成 /calendar/ 黄历页：月历网格 + 当日黄历。

农历、干支、节气、建除、星宿、宜忌等由 assets/lunar.js 在浏览器里计算。
本脚本只负责拼装页面并写入内联脚本的 CSP 哈希，改脚本后重跑即可。
"""

import base64
import hashlib
import pathlib
import sys

from build_pages import BASE_CSS

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "calendar" / "index.html"

CAL_CSS = """  .cal,.alm{ --seal:#a4402f }
  @media (prefers-color-scheme: dark){
    .cal,.alm{ --seal:#c9765f }
  }
  .page{
    max-width:60rem;
    margin:0 auto;
  }
  .cal{ margin:0 }
  .cal-bar{
    display:flex;
    justify-content:space-between;
    align-items:baseline;
    gap:12px;
    padding:18px 0 10px;
    border-bottom:1px solid var(--rule);
  }
  .cal-title{
    margin:0;
    font-size:1rem;
    font-weight:400;
    letter-spacing:.16em;
    font-variant-numeric:tabular-nums;
  }
  .nav{ display:flex; gap:14px }
  .nav button{
    padding:2px 0;
    border:0;
    background:none;
    color:var(--muted);
    font:inherit;
    font-size:.86rem;
    letter-spacing:.1em;
    cursor:pointer;
  }
  .nav button:hover{ color:var(--ink) }
  .week{
    display:grid;
    grid-template-columns:repeat(7,1fr);
    margin:12px 0 6px;
    font-size:.7rem;
    color:var(--muted);
    text-align:center;
    letter-spacing:.14em;
  }
  .grid{
    display:grid;
    grid-template-columns:repeat(7,1fr);
    border-top:1px solid var(--line);
    border-left:1px solid var(--line);
  }
  .cell{
    display:block;
    width:100%;
    min-height:62px;
    padding:7px 2px 6px;
    border:0;
    border-right:1px solid var(--line);
    border-bottom:1px solid var(--line);
    background:none;
    color:inherit;
    font:inherit;
    text-align:center;
    cursor:pointer;
  }
  .cell:hover{ background:var(--line) }
  .cell b{
    display:block;
    font-weight:400;
    font-size:1rem;
    line-height:1.3;
    font-variant-numeric:tabular-nums;
  }
  .cell span{
    display:block;
    font-size:.62rem;
    line-height:1.5;
    color:var(--muted);
  }
  .cell.jq span{ color:var(--seal) }
  .cell.out{ opacity:.3 }
  .cell.on,
  .cell.on:hover{ background:var(--ink); color:var(--paper) }
  .cell.on span{ color:var(--paper); opacity:.72 }
  .alm{
    margin:40px 0 0;
    padding-top:24px;
    border-top:1px solid var(--rule);
  }
  .alm-head{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:8px;
  }
  .alm-head p{
    margin:0;
    text-align:center;
    font-size:.8rem;
    letter-spacing:.12em;
    color:var(--muted);
    font-variant-numeric:tabular-nums;
  }
  .alm-head b{
    font-weight:400;
    color:var(--ink);
    letter-spacing:.06em;
  }
  .alm-step{
    flex:none;
    width:2.4em;
    padding:.1em 0;
    font:inherit;
    font-size:1.05rem;
    line-height:1.6;
    color:var(--muted);
    background:none;
    border:0;
    cursor:pointer;
  }
  .alm-step:hover{ color:var(--seal) }
  .alm-tags{
    margin:9px 0 0;
    text-align:center;
    font-size:.74rem;
    letter-spacing:.2em;
    color:var(--seal);
  }
  .alm-day{
    margin:10px 0 0;
    text-align:center;
  }
  .alm-day em{
    display:block;
    font-style:normal;
    font-size:.8rem;
    letter-spacing:.4em;
    text-indent:.4em;
    color:var(--muted);
  }
  .alm-day b{
    display:block;
    font-weight:400;
    font-size:clamp(2.8rem,1.6rem + 4.4vw,4.6rem);
    line-height:1.06;
    letter-spacing:.02em;
    color:var(--seal);
  }
  .alm-day span{
    display:block;
    margin-top:3px;
    font-size:.74rem;
    letter-spacing:.1em;
    color:var(--muted);
  }
  .alm-yiji{
    margin:24px 0 0;
    border-top:1px solid var(--line);
    border-bottom:1px solid var(--line);
  }
  .alm-yiji div{
    display:flex;
    align-items:flex-start;
    gap:12px;
    padding:11px 2px 12px;
  }
  .alm-yiji div + div{ border-top:1px solid var(--line) }
  .alm-yiji dt{
    flex:none;
    display:flex;
    align-items:center;
    justify-content:center;
    width:1.95em;
    height:1.95em;
    font-size:.78rem;
    color:var(--seal);
    border:1px solid var(--seal);
    border-radius:50%;
  }
  .alm-yiji div + div dt{
    color:var(--ink);
    border-color:var(--ink);
  }
  .alm-yiji dd{
    margin:0;
    padding-top:.15em;
    font-size:.86rem;
    line-height:1.85;
    letter-spacing:.05em;
  }
  .alm-table{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    margin:22px 0 0;
    border-top:1px solid var(--line);
    border-left:1px solid var(--line);
  }
  .alm-table div{
    padding:8px 11px 10px;
    border-right:1px solid var(--line);
    border-bottom:1px solid var(--line);
  }
  .alm-table .all{ grid-column:1 / -1 }
  .alm-table em{
    display:block;
    font-style:normal;
    font-size:.66rem;
    letter-spacing:.18em;
    color:var(--muted);
  }
  .alm-table b{
    display:block;
    margin-top:2px;
    font-weight:400;
    font-size:.8rem;
    line-height:1.75;
    letter-spacing:.04em;
  }
  .alm-sub{
    margin:26px 0 9px;
    font-size:.7rem;
    letter-spacing:.34em;
    text-indent:.34em;
    color:var(--muted);
  }
  .times{
    display:grid;
    grid-template-columns:repeat(6,1fr);
    border-top:1px solid var(--line);
    border-left:1px solid var(--line);
  }
  .times div{
    padding:8px 4px 9px;
    border-right:1px solid var(--line);
    border-bottom:1px solid var(--line);
    text-align:center;
  }
  .times b{
    display:block;
    font-weight:400;
    font-size:.84rem;
    letter-spacing:.06em;
  }
  .times span{
    display:block;
    font-size:.56rem;
    color:var(--muted);
    font-variant-numeric:tabular-nums;
    white-space:nowrap;
  }
  .times i{
    display:block;
    margin-top:2px;
    font-style:normal;
    font-size:.62rem;
    letter-spacing:.08em;
    color:var(--muted);
  }
  .times i.ok{ color:var(--seal) }
  .times div.now{ background:var(--ink); color:var(--paper) }
  .times div.now span,
  .times div.now i,
  .times div.now i.ok{ color:var(--paper); opacity:.72 }
  .noscript{ margin:20px 0 0; color:var(--muted); font-size:.86rem }
  @media (max-width:560px){
    .page{ padding-left:24px; padding-right:24px }
    .cell{ min-height:54px }
    .cell b{ font-size:.94rem }
    .alm-table{ grid-template-columns:1fr 1fr }
    .times{ grid-template-columns:repeat(4,1fr) }
  }
"""

CAL_JS = """(function(){
  "use strict";
  var Solar=window.Solar;
  if(!Solar){ return; }
  var W="日一二三四五六";
  var grid=document.querySelector("[data-grid]");
  var mh=document.querySelector("[data-mh]");
  var det=document.querySelector("[data-detail]");

  function pad(n){ return (n<10?"0":"")+n; }
  function key(d){ return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate()); }
  function fromHash(){
    var m=/^#(\\d{4})-(\\d{1,2})-(\\d{1,2})$/.exec(location.hash||"");
    if(!m){ return null; }
    var y=+m[1],mo=+m[2],da=+m[3];
    if(mo<1||mo>12||da<1||da>31){ return null; }
    var d=new Date(y,mo-1,da);
    if(d.getFullYear()!==y||d.getMonth()!==mo-1||d.getDate()!==da){ return null; }
    return d;
  }
  function lunarOf(y,m,d){
    try{ return Solar.fromYmd(y,m,d).getLunar(); }catch(e){ return null; }
  }

  var sel=fromHash()||new Date();
  var vy=sel.getFullYear(), vm=sel.getMonth();

  function paintGrid(){
    var start=new Date(vy,vm,1);
    start=new Date(vy,vm,1-start.getDay());
    var out="",i,d,y,mo,da,lu,jq,sub,cls;
    for(i=0;i<42;i++){
      d=new Date(start.getFullYear(),start.getMonth(),start.getDate()+i);
      y=d.getFullYear(); mo=d.getMonth()+1; da=d.getDate();
      lu=lunarOf(y,mo,da);
      jq=""; sub="";
      if(lu){
        jq=lu.getJieQi();
        if(jq){ sub=jq; }
        else if(da===1){ sub=lu.getMonthInChinese()+"月"; }
        else { sub=lu.getDayInChinese(); }
      }
      cls="cell";
      if(d.getMonth()!==vm){ cls+=" out"; }
      if(y===sel.getFullYear()&&mo===sel.getMonth()+1&&da===sel.getDate()){ cls+=" on"; }
      if(jq){ cls+=" jq"; }
      out+='<button type="button" class="'+cls+'" data-d="'+key(d)+'"><b>'+da+"</b><span>"+sub+"</span></button>";
    }
    grid.innerHTML=out;
    mh.textContent=vy+" 年 "+(vm+1)+" 月";
  }

  function cell(k,v,c){ return '<div'+(c?' class="'+c+'"':'')+'><em>'+k+"</em><b>"+v+"</b></div>"; }
  function list(arr){ return arr&&arr.length?arr.join("　"):"—"; }
  function week(y,mo,da){
    var d=new Date(y,mo-1,da),j=new Date(y,0,1);
    return Math.floor((Math.floor((d-j)/864e5)+j.getDay())/7)+1;
  }
  function cn(n){
    var d="〇一二三四五六七八九",s="",i,x=String(n);
    for(i=0;i<x.length;i++){ s+=d.charAt(+x.charAt(i)); }
    return s;
  }
  function rng(i){ return pad(i?2*i-1:23)+":00–"+pad(i?2*i:0)+":59"; }
  function times(lu,cur){
    var t=lu.getTimes(),out="",i,x,luck;
    for(i=0;i<12;i++){
      x=t[i];
      luck=x.getTianShenLuck();
      out+='<div'+(i===cur?' class="now"':"")+'><b>'+x.getGanZhi()+'</b><span>'+x.getZhi()+"时 "+rng(i)+'</span><i'+
        (luck==="吉"?' class="ok"':"")+">"+x.getTianShen()+" "+luck+"</i></div>";
    }
    return out;
  }

  function paintDay(){
    var y=sel.getFullYear(),mo=sel.getMonth()+1,da=sel.getDate();
    var so,lu;
    try{ so=Solar.fromYmd(y,mo,da); lu=so.getLunar(); }catch(e){ det.innerHTML=""; return; }
    var tags=lu.getFestivals().concat(so.getFestivals());
    if(lu.getJieQi()){ tags.unshift(lu.getJieQi()); }
    var now=new Date();
    var today=y===now.getFullYear()&&mo===now.getMonth()+1&&da===now.getDate();
    var html='<div class="alm-head">'+
      '<button type="button" class="alm-step" data-day="-1" aria-label="前一天">‹</button>'+
      "<p><b>"+y+" 年 "+mo+" 月 "+da+" 日</b><span>星期"+W[so.getWeek()]+
      " · 第 "+week(y,mo,da)+" 周</span></p>"+
      '<button type="button" class="alm-step" data-day="1" aria-label="后一天">›</button></div>';
    if(tags.length){ html+='<p class="alm-tags">'+tags.join(" · ")+"</p>"; }
    var cur=today?Math.floor(((now.getHours()+1)%24)/2):-1;
    html+='<div class="alm-day"><em>'+lu.getMonthInChinese()+"月</em><b>"+lu.getDayInChinese()+
      "</b><span>"+lu.getYearInGanZhiExact()+"年 "+lu.getMonthInGanZhiExact()+"月 "+
      lu.getDayInGanZhi()+"日 · 属"+lu.getYearShengXiao()+" · 道历 "+cn(lu.getYear()+2697)+
      " 年</span></div>";
    html+='<dl class="alm-yiji"><div><dt>宜</dt><dd>'+list(lu.getDayYi())+"</dd></div>"+
      "<div><dt>忌</dt><dd>"+list(lu.getDayJi())+'</dd></div></dl><div class="alm-table">'+
      cell("纳音",lu.getDayNaYin())+
      cell("冲煞","冲"+lu.getDayChongDesc()+" 煞"+lu.getDaySha())+
      cell("值神",lu.getDayTianShen())+
      cell("建除",lu.getZhiXing()+"日")+
      cell("星宿",lu.getXiu()+lu.getZheng()+lu.getAnimal())+
      cell("胎神",lu.getDayPositionTai())+
      cell("吉神宜趋",lu.getDayJiShen().join("　"),"all")+
      cell("凶煞宜忌",lu.getDayXiongSha().join("　"),"all")+
      cell("喜神",lu.getDayPositionXiDesc())+
      cell("福神",lu.getDayPositionFuDesc())+
      cell("财神",lu.getDayPositionCaiDesc())+
      cell("彭祖百忌",lu.getPengZuGan()+"　"+lu.getPengZuZhi(),"all")+
      '</div><p class="alm-sub">十二时辰吉凶</p><div class="times">'+times(lu,cur)+"</div>";
    det.innerHTML=html;
  }

  det.addEventListener("click",function(e){
    var b=e.target;
    while(b&&b!==det&&!b.getAttribute("data-day")){ b=b.parentNode; }
    if(!b||b===det){ return; }
    var d=new Date(sel.getTime());
    d.setDate(d.getDate()+ +b.getAttribute("data-day"));
    location.hash="#"+key(d);
  });

  grid.addEventListener("click",function(e){
    var b=e.target;
    while(b&&b!==grid&&!b.getAttribute("data-d")){ b=b.parentNode; }
    if(!b||b===grid){ return; }
    var p=b.getAttribute("data-d").split("-");
    sel=new Date(+p[0],+p[1]-1,+p[2]);
    vy=sel.getFullYear(); vm=sel.getMonth();
    if(location.hash!=="#"+key(sel)){ location.hash=key(sel); }
    paintGrid(); paintDay();
  });

  var steps=document.querySelectorAll("[data-step]");
  for(var i=0;i<steps.length;i++){
    steps[i].addEventListener("click",function(){
      vm+=+this.getAttribute("data-step");
      if(vm<0){ vm=11; vy--; }
      if(vm>11){ vm=0; vy++; }
      paintGrid();
    });
  }

  var today=document.querySelector("[data-today]");
  if(today){
    today.addEventListener("click",function(){
      sel=new Date();
      vy=sel.getFullYear(); vm=sel.getMonth();
      if(location.hash!=="#"+key(sel)){ location.hash=key(sel); }
      paintGrid(); paintDay();
    });
  }

  window.addEventListener("hashchange",function(){
    var d=fromHash();
    if(!d){ return; }
    sel=d; vy=sel.getFullYear(); vm=sel.getMonth();
    paintGrid(); paintDay();
  });

  paintGrid(); paintDay();
})();"""

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta http-equiv="Content-Security-Policy" content="__CSP__">
<meta name="referrer" content="no-referrer">
<title>黄历 · bihongcue876</title>
<meta name="description" content="公历与农历对照、干支、节气、建除与宜忌，按日查看。">
<style>
__CSS__
</style>
</head>
<body>
<div class="page">
  <header class="masthead">
    <p class="mark"><a href="/">— B . H . C —</a></p>
    <p class="since">since 2020.</p>
  </header>

  <main>
    <section class="cal" aria-label="月历">
      <div class="cal-bar">
        <h1 class="cal-title" data-mh>—</h1>
        <div class="nav">
          <button type="button" data-step="-1" aria-label="上一月">‹</button>
          <button type="button" data-today>今天</button>
          <button type="button" data-step="1" aria-label="下一月">›</button>
        </div>
      </div>
      <div class="week" aria-hidden="true">
        <span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span>
      </div>
      <div class="grid" data-grid></div>
      <noscript><p class="noscript">本页需要脚本才能计算农历与宜忌。</p></noscript>
    </section>

    <section class="alm" data-detail aria-label="当日黄历"></section>
  </main>

  <footer class="site-footer">
    <span>© 2026</span>
    <a href="/">← 首页</a>
  </footer>
</div>
<script src="/assets/lunar.js"></script>
__SCRIPT__
</body>
</html>
"""


def digest(js):
    return base64.b64encode(hashlib.sha256(js.encode("utf-8")).digest()).decode("ascii")


def build():
    js = CAL_JS
    csp = (
        "default-src 'none'; script-src 'self' 'sha256-%s'; "
        "style-src 'unsafe-inline'; img-src 'self' data:; "
        "base-uri 'none'; form-action 'none'" % digest(js)
    )
    html = PAGE.replace("__CSP__", csp)
    html = html.replace("__CSS__", BASE_CSS + CAL_CSS)
    html = html.replace("__SCRIPT__", "<script>" + js + "</script>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    return OUT


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    out = build()
    print("生成 %-24s %d 字节" % (out.relative_to(ROOT).as_posix(), out.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
