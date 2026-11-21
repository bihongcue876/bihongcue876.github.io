# bihongcue876.github.io

个人主页，GitHub Pages 直接发布本仓库 `main` 分支根目录。

站点：<https://bihongcue876.github.io/>

## 结构

| 路径 | 内容 |
| --- | --- |
| `index.html` | 首页：页头标记、主句、说明、组件框、五个分区入口；单文件，含一个内联时钟脚本 |
| `projects/` `works/` `writings/` `resources/` `about/` | 五个分区页，由 `data/` 下的 JSON 生成，产物一并提交 |
| `data/*.json` | 分区条目登记：项目、作品、文稿、资源、关于 |
| `scripts/build_pages.py` | 读 `data/*.json`，生成五个分区页 |
| `heatmap/index.html` | 年度提交热力图，由脚本生成，数据内联 |
| `heatmap-data.json` | 同一份热力图数据的纯 JSON 快照 |
| `calendar/index.html` | 黄历：月历网格与当日干支、节气、建除、宜忌，由 `scripts/build_calendar.py` 生成 |
| `assets/lunar.js` | 黄历页使用的农历库 lunar-javascript v1.7.8（MIT，© 6tail） |
| `scripts/` | 取数与渲染脚本（随站点公开，见下方说明） |
| `404.html` / `robots.txt` | 站点元文件 |

## 分区形式

五个分区共用同一套页头（`— B . H . C —` / `since 2020.`）、页脚、色板与衬线字体栈，只换正文布局。

| 分区 | 布局 | 形态 |
| --- | --- | --- |
| 项目 `01` | `indexed` | 编号 + 题名 + 说明 + 右侧状态，按状态分组 |
| 作品 `02` | `plates` | 左竖线图版，题名大字，不分组 |
| 文稿 `03` | `toc` | 书目录式，点线引到日期，按卷分组 |
| 资源 `04` | `list` | 两栏网格，行距更紧，带类型后缀 |
| 关于 `05` | `prose` | 单栏长文 + 定义列表，无条目 |

条目字段见各 `data/*.json`。公共字段：`title`、`href`（可选，缺省时渲染成纯文本行）。

## 更新

改分区内容：

```bash
python scripts/build_pages.py          # 全量重写五个分区页
python scripts/build_pages.py works    # 只重写一个
```

热力图由本机 WSL 定时生成并推送，本站不做在线构建：

```bash
scripts/update.sh          # 取数、重绘、有变化才提交并推送
scripts/update.sh --dry    # 只重绘并查看 diff
```

Windows 侧可双击 `scripts/refresh.cmd` 走同一流程。日志写在 `.heatmap.log`（已忽略）。

## 数据口径

只统计 commit 次数；不读取仓库名、issue/PR 标题与提交内容。口径实现见 `scripts/heatmap.py`。

## 说明

首页与五个分区页不含脚本；黄历页与热力图页各带一段内联脚本，黄历页另加载同源的 `assets/lunar.js`。页面不加载第三方资源；外部请求只可能由「资源」页里明确列出的链接发起。本地预览：

```bash
python -m http.server 8765
```

GitHub Pages 会把站点仓库根目录的文件全部作为静态资源公开，因此 `scripts/` 下的脚本（含本机路径）对外可读；如需保密，应把脚本移到私有仓库，本站只保留产物。
