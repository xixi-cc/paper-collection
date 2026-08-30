# Paper Collection-Xncao

一个可搜索、可筛选的个人论文收藏站，部署在 GitHub Pages。

## 网站用途与功能

本站收录个人长期关注、收藏的文章，以及感兴趣的学者收藏的文章。网站的制作灵感来自 [刘子鸣的 Paper Collection](https://metacircleai.github.io/ziming-paper-collection/collection.html)。

## 阅读与订阅

- 点击论文右侧星标可在当前浏览器收藏，并可导出或导入 JSON 备份；
- 使用“只看收藏”筛选已保存论文；
- `feed.xml` 提供最近收录论文的 Atom 订阅；
- 具有全文 Paper Card 的论文可进入详情页参与 GitHub Discussions 评论。

## 许可与引用

原创分类、选编、注释和论文卡片解读采用 CC BY-NC 4.0；原创应用代码采用
MIT。摘要、引文、图表和论文正文等第三方内容不在本站授权范围内。完整边界见
[`LICENSE.md`](LICENSE.md)，推荐引用格式见 [`CITATION.md`](CITATION.md) 和
[`CITATION.cff`](CITATION.cff)。引用卡片时仍须另外引用原始论文。

## 添加文章

编辑 `public/papers.json`，复制一条现有记录并修改内容。每条记录包含：

- `id`：稳定且唯一的标识，arXiv 文章建议直接使用 arXiv ID；
- `date`：收录日期，格式为 `YYYY-MM-DD`；
- `published`：论文发表日期，可使用 `YYYY`、`YYYY-MM` 或 `YYYY-MM-DD`；
- `title`：页面中显示的文章题目；
- `url`：默认论文页面；
- `links`：可选的正式发表页（`publication`）和 arXiv 页面（`arxiv`）；已正式发表的 arXiv 论文同时保留两种链接；
- `tags`：固定为两个标签，依次为来源（source）和主题（topic）。
- `curation_sources`：可选的策展来源数组，记录公开收藏名称与链接；它与论文的发表来源分开保存。

页面默认按正式发表日期排序。若尚未正式发表，则使用 arXiv 初次提交日期；也可按 topic、收录日期或标题排序。

## Topic 规则

每篇文章只保留一个 topic。`scripts/assign_topics.py` 使用受控主题表：明确的方法或研究领域（例如 `Neural Operators`、`Flow Matching`、`Renormalization Group`、`Active Matter`）优先于宽泛分类；没有更强规则时才保留已有人工分类。歧义标题使用可审计的显式覆盖，不使用 `Other` 作为默认兜底。

提交到 `main` 分支后，GitHub Actions 会自动重新发布网站。

Every completed website update must be pushed to GitHub. 此规则适用于论文元数据、Paper Card 链接、界面、脚本和部署配置。完成更新必须经过校验与构建、提交、无强制推送到 GitHub `origin/main`、确认本地 `HEAD` 与 GitHub 分支头一致，并核验 GitHub Actions / Pages。OpenAI Sites 只是并行发布目标，不能代替 GitHub 同步；同时发布时二者必须来自同一份已验证源码树。

## 本地预览

```bash
npm install
npm run dev
```

## 构建检查

```bash
npm run build
```
