<div align="center">

# 高性价比人生 2.0 · 可搜索版

**672 条生活建议，不用一页一页地看——想到什么搜什么，一秒直达。**

<br>

## 👉 [**点这里直接打开网站使用：https://life.daogong.cc**](https://life.daogong.cc)

**不用下载、不用装任何东西，打开就能搜。** 输入你遇到的事——

> 「租房合同」「房东不退押金」「食品安全」「尿血」「烫食」「炒股」「AB贷」「被骗了」「煤气泄漏」……

**每一搜都直接命中具体条目**：花掉什么、换回什么、证据有多硬、该怎么做，一页看全。

<br>

[![在线检索](https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E6%A3%80%E7%B4%A2-%E7%82%B9%E5%87%BB%E7%9B%B4%E6%8E%A5%E4%BD%BF%E7%94%A8-3451b2?style=flat-square)](https://life.daogong.cc)
[![条目](https://img.shields.io/badge/%E6%9D%A1%E7%9B%AE-672%20%E6%9D%A1-18794e?style=flat-square)](#本项目优点)
[![上游](https://img.shields.io/badge/%E4%B8%8A%E6%B8%B8-HowToLiveBetter-565a5f?style=flat-square)](https://github.com/eternity4719/HowToLiveBetter)

</div>

---

## 这是什么

上游书 [高性价比人生指南](https://github.com/eternity4719/HowToLiveBetter)（672 条建议，证据分级，来源只引期刊论文和官方文件）的**可搜索静态站**。

书里的内容按「1. 不要早死 → 2. 不要慢慢死 → …」的章节排，一条条翻很费劲；这个网站把它变成**搜索引擎**：用生活化、口语化的词搜，直接到条目。

## 本项目优点

- **🔎 想到什么搜什么**：口语/场景词直接命中——「房东不退押金」「AB贷」「尿血」「食品安全」都不用猜关键词
- **⚡ 一秒直达**：点搜索结果直接看全文（正文全在本站），不用跳转、不用注册、不用登录
- **⚖️ BM25 智能权重**：稀有词票重、常见词票轻，搜「食品安全」不会混进一堆不相关的
- **🎯 精确意图优先**：搜「租房合同」直接到押金合同条目，不被同义词带偏
- **📱 手机也能用**：纯静态页面，零构建零后端，打开即搜
- **🔓 完全免费**：无广告追踪（预留广告位但默认关闭）、无注册、数据全开放
- **🔄 自动续补**：上游新增内容自动生成关键词库，搜索范围跟着长
- **📖 保留出处**：每条都能一键跳回 GitHub 原文，协议合规（CC BY 4.0）

## 特性

- 🔍 **四层评分**：词典逆向命中 → keywords 直通（exact 档 +8 / 普通档 +3）→ 长词包含 → 2-gram 兜底
- ⚖️ **BM25 idf 加权**：df 表预计算（全库 2 字 gram + 整词），稀有词票重、常见词票轻，根治「食品安全」类常见词淹没稀有词
- 🎯 **直通两档**：query 完全等于键（如「租房合同」）走 exact 档高权重，压过同义词噪音
- 🔄 **同义词远义词降权**：query 有直通映射时，远义词打 0.4 折（两阶段召回思路）
- 📉 **降级安全**：df.json 加载失败自动降级旧评分，不报错
- 📊 **672 条全量数据**：关键词/同义词/场景胶囊自动从正文生成，上游新增内容自动续补

## 快速开始

```bash
# 直接部署 site/ 目录到任意静态服务器即可，零构建
# 本地预览
cd site && python3 -m http.server 8080
```

## 重建数据（上游更新后）

```bash
cd scripts
python3 pipeline.py    # 重建条目 → 生成关键词/同义词/胶囊 → 重算 df 表 → 全量校验
python3 test_search.py # 59 句搜索回归（BM25 模式）
```

## 目录结构

```
site/       纯静态站（发布物，零构建直接挂）
scripts/    数据管线（重建/关键词生成/BM25 df 表/回归测试）
data/       生成的数据（search-index/keywords/synonyms/scenes/df.json）
```

## 许可

- **正文**来自上游 [高性价比人生指南](https://github.com/eternity4719/HowToLiveBetter)，用 [CC BY 4.0](LICENSE) 发布。
- **搜索管线代码**用 [MIT](LICENSE-CODE) 发布。
- 本站是上游的衍生作品（改过内容：转为可搜索静态站 + 关键词库重写），同步的上游版本见 [上游仓库](https://github.com/eternity4719/HowToLiveBetter)。

## 致谢

- 上游作者 [eternity4719](https://github.com/eternity4719) 的 672 条生活建议
- [Claude Code](https://claude.com/claude-code) 协助编写上游书稿
