<div align="center">

# 高性价比人生 2.0 · 可搜索版

**672 条生活建议，生活化关键词一搜就到。** 用最少的钱、时间和精力，换回最多的寿命、金钱和人身自由。

[![在线检索](https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E6%A3%80%E7%B4%A2-life.daogong.cc-3451b2?style=flat-square)](https://life.daogong.cc)
[![条目](https://img.shields.io/badge/%E6%9D%A1%E7%9B%AE-672%20%E6%9D%A1-18794e?style=flat-square)](#特性)
[![上游](https://img.shields.io/badge/%E4%B8%8A%E6%B8%B8-HowToLiveBetter-565a5f?style=flat-square)](https://github.com/eternity4719/HowToLiveBetter)

**👉 网站地址：[https://life.daogong.cc](https://life.daogong.cc)**

</div>

---

## 这是什么

上游书 [高性价比人生指南](https://github.com/eternity4719/HowToLiveBetter)（672 条建议，证据分级，来源只引期刊论文和官方文件）的**可搜索静态站**：

- **生活化搜索**：用口语/场景词搜——「食品安全」「租房合同」「房东不退押金」「AB贷」「尿血」「炒股」都能精准命中
- **搜索技术**：BM25 逆文档频率加权（稀有词票重、常见词票轻）+ 场景关键词直通 + 同义词扩展 + 2-gram 兜底，纯前端零构建零后端
- **全文本地**：正文放本站直接看，点「在 GitHub 查看原文 ↗」才跳作者
- **零依赖**：纯静态 HTML + 原生 JS，无 jieba/无外部搜索库/无框架

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
