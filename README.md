<div align="center">

# 高性价比人生 2.0 · 可搜索版

**765 条生活建议，不用一页一页地看——想到什么搜什么，一秒直达。**

<br>

## 👉 [**点这里直接打开网站使用：https://life.daogong.cc**](https://life.daogong.cc)

**不用下载、不用装任何东西，打开就能搜。** 输入你遇到的事——

> 「租房合同」「房东不退押金」「食品安全」「尿血」「烫食」「炒股」「AB贷」「被骗了」「煤气泄漏」……

**每一搜都直接命中具体条目**：花掉什么、换回什么、证据有多硬、该怎么做，一页看全。

<br>

[![在线检索](https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E6%A3%80%E7%B4%A2-%E7%82%B9%E5%87%BB%E7%9B%B4%E6%8E%A5%E4%BD%BF%E7%94%A8-3451b2?style=flat-square)](https://life.daogong.cc)
[![条目](https://img.shields.io/badge/%E6%9D%A1%E7%9B%AE-765%20%E6%9D%A1-18794e?style=flat-square)](#本项目优点)
[![上游](https://img.shields.io/badge/%E4%B8%8A%E6%B8%B8-HowToLiveBetter-565a5f?style=flat-square)](https://github.com/eternity4719/HowToLiveBetter)

</div>

---

## 这是什么

上游书 [高性价比人生指南](https://github.com/eternity4719/HowToLiveBetter)（**765 条**建议，证据分级，来源只引期刊论文和官方文件）的**可搜索静态站**。

书里的内容按「1. 不要早死 → 2. 不要慢慢死 → …」的章节排，一条条翻很费劲；这个网站把它变成**搜索引擎**：用生活化、口语化的词搜，直接到条目。

## 本项目优点

- **🔎 想到什么搜什么**：口语/场景词直接命中——「房东不退押金」「AB贷」「尿血」「食品安全」都不用猜关键词
- **⚡ 一秒直达**：点搜索结果直接看全文（正文全在本站），不用跳转、不用注册、不用登录
- **⚖️ BM25 智能权重**：稀有词票重、常见词票轻，搜「食品安全」不会混进一堆不相关的
- **🎯 精确意图优先**：搜「租房合同」直接到押金合同条目，不被同义词带偏
- **🔗 每条都有独立网页**：765 个条目的正文被**预渲染成静态页**（`/detail/<id>.html`），带标题、摘要、规范链接（canonical）——不开 JavaScript 也能读到完整内容，搜索引擎和分享链接都友好
- **📱 手机也能用**：纯静态页面，零构建零后端，打开即搜
- **🔓 完全免费**：无广告追踪（预留广告位但默认关闭）、无注册、数据全开放
- **🔄 自动续补**：上游新增内容自动生成关键词库，搜索范围跟着长（另有独立监工脚本，同步断档会告警）
- **📖 保留出处**：每条都能一键跳回 GitHub 原文，协议合规（CC BY 4.0）

## 特性

- 🔍 **四层评分**：词典逆向命中 → keywords 直通（exact 档 +8 / 普通档 +3）→ 长词包含 → 2-gram 兜底
- ⚖️ **BM25 idf 加权**：df 表预计算（全库 2 字 gram + 整词），稀有词票重、常见词票轻，根治「食品安全」类常见词淹没稀有词
- 🎯 **直通两档**：query 完全等于键（如「租房合同」）走 exact 档高权重，压过同义词噪音
- 🔄 **同义词远义词降权**：query 有直通映射时，远义词打 0.4 折（两阶段召回思路）
- 📉 **降级安全**：df.json 加载失败自动降级旧评分，不报错
- 🧪 **双端同源门禁**：Python 参考实现与前端正身 JS 跑**同一套 59 句用例**（`tests/cases.json`），改搜索逻辑前后各有拦截
- 🕵️ **robots 不挡自己的渲染资源**：全站 `Allow: /`，只**逐文件**屏蔽内部构建文件——避免「页面渲染要用的 JS/数据被爬虫屏蔽 → 页面全是空壳」这类自伤
- 📝 **sitemap 真实化**：770 条 URL 指向静态详情页；`lastmod` 按**内容变化**刷新（不是每次重建都刷成今天）

## 快速开始

```bash
# 直接部署 site/ 目录到任意静态服务器即可，零构建
# 本地预览（本项目前端用绝对路径 /core/… 与 /data/…，请在 site/ 内起服务）
cd site && python3 -m http.server 8080   # 然后打开 http://localhost:8080
```

## 重建数据（上游更新后）

```bash
# 全链路：拉上游 → 校验 LICENSE → 重建条目 → 关键词/场景词 → df 表 → 预渲染静态页 → 全套门禁
python3 scripts/pipeline.py
python3 scripts/check_freshness.py     # 独立监工：同步是否断档（健康时零输出）

# 门禁（改搜索逻辑后必跑）
python3 scripts/test_search.py         # 59 句回归（BM25 模式，必须带 df.json）
python3 scripts/verify_entries.py      # 全量入口词：0 结果 / 悬空 / 标点键
python3 scripts/verify_deploy.py       # 发布物自洽：数据同步 / sitemap 覆盖 / robots 放行渲染链 / 内部文件未发布
node tests/front_gate.mjs              # 前端正身门禁（需 node，跑 site/core/search.js 真身）
bash deploy/verify_remote.sh https://你的域名 765   # 远端部署后断言（36 项）
```

## 目录结构

```
site/              纯静态站（发布物，零构建直接挂）
  ├─ index.html    首页 + 结果页（同页视图切换）
  ├─ detail.html   旧式详情页（?id=），仍兼容
  ├─ detail/       765 个预渲染静态详情页（/detail/<id>.html）
  ├─ core/         原生 JS：search.js（搜索正身）/ detail.js / footer.js / ads*.js
  ├─ data/         前端真正 fetch 的数据（search-index/synonyms/keywords/scenes/df/meta + sec-*.json）
  ├─ pages/        合规四页（about/privacy/terms/contact）
  └─ robots.txt / sitemap.xml / ads.txt
scripts/           数据管线（抓取/重建/关键词/df 表/预渲染/门禁/监工）
data/              生成的数据与构建输入（含内部构建源，前端不直接 fetch）
tests/             双端共用用例 + 前端正身门禁夹具
deploy/            部署后断言脚本
```

## 许可

- **正文**来自上游 [高性价比人生指南](https://github.com/eternity4719/HowToLiveBetter)，用 [CC BY 4.0](LICENSE) 发布。
- **搜索管线代码**用 [MIT](LICENSE-CODE) 发布。
- 本站是上游的衍生作品（改过内容：转为可搜索静态站 + 关键词库重写 + 预渲染），同步的上游版本见 [上游仓库](https://github.com/eternity4719/HowToLiveBetter)。

## 致谢

- 上游作者 [eternity4719](https://github.com/eternity4719) 的 765 条生活建议
- [Claude Code](https://claude.com/claude-code) 协助编写上游书稿
