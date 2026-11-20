#!/usr/bin/env python3
"""体检 gh 到底能看到多少贡献：逐年日历总数、受限（私有）数量、仓库数。

在已登录 gh 的环境里跑：
    python3 scripts/diagnose.py
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys

Q = """query($from:DateTime!,$to:DateTime!){
  viewer {
    login
    contributionsCollection(from:$from,to:$to){
      hasAnyRestrictedContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
  }
}"""


def gh(args):
    r = subprocess.run(["gh", "api"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit((r.stderr or r.stdout).strip() or "gh 调用失败")
    return r.stdout


def main():
    me = json.loads(gh(["user"]))["login"]
    print("账号：%s" % me)

    r = subprocess.run(["gh", "repo", "list", "--limit", "400",
                        "--json", "nameWithOwner,isPrivate"],
                       capture_output=True, text=True)
    try:
        repos = json.loads(r.stdout or "[]")
    except ValueError:
        repos = []
    priv = [x for x in repos if x.get("isPrivate")]
    print("仓库：%d 个，其中私有 %d 个" % (len(repos), len(priv)))
    if repos:
        print("私有仓库：" + ("、".join(x["nameWithOwner"] for x in priv[:12]) or "无"))

    today = dt.date.today()
    print("\n年份   日历总数   受限(私有)   有受限")
    tot_all = tot_res = 0
    for y in range(2015, today.year + 1):
        raw = gh(["graphql", "-f", "query=" + Q,
                  "-f", "from=%04d-01-01T00:00:00Z" % y,
                  "-f", "to=%04d-12-31T23:59:59Z" % y])
        c = json.loads(raw)["data"]["viewer"]["contributionsCollection"]
        tot = c["contributionCalendar"]["totalContributions"]
        res = c["restrictedContributionsCount"]
        tot_all += tot
        tot_res += res
        print("%4d   %8d   %9d   %s" % (
            y, tot, res, "是" if c["hasAnyRestrictedContributions"] else "-"))

    print("\n合计：日历 %d 次，其中受限 %d 次" % (tot_all, tot_res))
    print("\n判读：")
    print("  日历总数 ≈ 你印象里的次数 → 数据没问题，直接跑 update.sh")
    print("  受限数占大头 → GitHub 设置里勾选 Include private contributions on my profile")
    print("  两者都远小于实际 → 提交在 fork 或非默认分支，要换「遍历仓库」的采集方式")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
