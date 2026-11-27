# bihongcue876.github.io

个人主页，GitHub Pages 直接发布本仓库 `main` 分支根目录。

站点：<https://bihongcue876.github.io/>

## 结构

| 路径 | 内容 |
| --- | --- |
| `index.html` | 首页：页头标记、主句、说明、组件框、五个分区入口；单文件，含一个内联时钟脚本 |
| `projects/` `works/` `writings/` `resources/` `about/` | 五个分区页，由 `data/` 下的 JSON 生成，产物一并提交 |
| `data/*.json` | 分区条目登记：项目、作品、文稿、工具与资源、关于 |
| `scripts/build_pages.py` | 读 `data/*.json`，生成五个分区页 |
| `scripts/build_article.py` | 读 `content/writings/*.html` 与 `data/writings.json`，生成文章页 |
| `scripts/build_search.py` | 生成 `search.json` 索引与 `/search/` 页面 |
| `search.json` / `search/` | 站内检索：索引 + 检索页，前端在本机匹配 |
| `content/writings/` | 文章正文片段，只写正文，页头页脚目录由脚本补 |
| `resources/riscv32i/` | RV32I 转码学习助手：纯前端工具页，脚本按 ES module 同源加载 |
| `projects/smallworld/` | 小世界寻路：Vite 构建产物，含 module worker；重新构建后需重套 CSP 与 `site.css` |
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
| 项目 `01` | `indexed` | 编号 + 题名 + 说明 + 右侧状态；每组带锚点与说明，条目可挂多个链接 |
| 作品 `02` | `plates` | 左竖线图版，题名大字，不分组 |
| 文稿 `03` | `toc` | 书目录式，点线引到日期，按卷分组；条目指到独立文章页 |
| 工具与资源 `04` | `list` | 两栏网格，行距更紧，带类型后缀 |
| 关于 `05` | `prose` | 单栏长文 + 定义列表，无条目 |

条目字段见各 `data/*.json`。公共字段：`title`、`href`（可选，缺省时渲染成纯文本行）。

`indexed`（项目页）另有分组字段：

| 字段 | 位置 | 作用 |
| --- | --- | --- |
| `groups[].id` | 分组 | 锚点名，生成 `#id`；两组以上自动出顶部分类导航 |
| `groups[].label` | 分组 | 分类标题 |
| `groups[].note` | 分组 | 分类说明，可用 `[文字](/路径/)` 写链接 |
| `groups[].empty` | 分组 | 条目为空时的占位文案，缺省「暂无条目」 |
| `items[].status` / `year` | 条目 | 行尾状态与年份 |
| `items[].links` | 条目 | 追加链接行：`[{"label":"源码","href":"https://…"}]` |

条目有 `href` 时整行可点，此时 `note` 按纯文本处理；要让说明里带链接，就不写 `href`，改用 `links`。编号 `no` 可省略，按组内序号自动补零。

## 更新

改分区内容：

```bash
python scripts/build_pages.py          # 全量重写五个分区页
python scripts/build_pages.py works    # 只重写一个
python scripts/build_article.py        # 全量重写文章页
python scripts/build_article.py riscv32i   # 只重写一篇
python scripts/build_search.py         # 重写检索索引与检索页
```

写一篇新文章：正文另存 `content/writings/<file>.html`，只写正文，标题用 `<h2 id="…">`、`<h3 id="…">`，段落与图照常写；再到 `data/writings.json` 的条目里补 `file`、`date`、`summary`，跑上面两条命令即可。目录、字数与文章页的页头页脚都由脚本生成，只有条目带 `file` 才会产出页面。

热力图由本机 WSL 定时生成并推送，本站不做在线构建：

```bash
scripts/update.sh          # 取数、重绘、有变化才提交并推送
scripts/update.sh --dry    # 只重绘并查看 diff
```

Windows 侧可双击 `scripts/refresh.cmd` 走同一流程。日志写在 `.heatmap.log`（已忽略）。

## 数据口径

只统计 commit 次数；不读取仓库名、issue/PR 标题与提交内容。口径实现见 `scripts/heatmap.py`。

## 说明

首页与五个分区页不含脚本；黄历页与热力图页各带一段内联脚本，黄历页另加载同源的 `assets/lunar.js`。页面不加载第三方资源；外部请求只可能由「工具与资源」页里明确列出的链接发起。本地预览：

```bash
python -m http.server 8765
```

GitHub Pages 会把站点仓库根目录的文件全部作为静态资源公开，因此 `scripts/` 下的脚本（含本机路径）对外可读；如需保密，应把脚本移到私有仓库，本站只保留产物。
