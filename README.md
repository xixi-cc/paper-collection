# Xixi's Paper Collection

一个可搜索、可筛选的个人论文收藏站，部署在 GitHub Pages。

## 添加文章

编辑 `public/papers.json`，复制一条现有记录并修改内容。每条记录包含：

- `id`：稳定且唯一的标识，arXiv 文章建议直接使用 arXiv ID；
- `date`：收录日期，格式为 `YYYY-MM-DD`；
- `published`：论文发表日期，可使用 `YYYY`、`YYYY-MM` 或 `YYYY-MM-DD`；
- `title`：页面中显示的文章题目；
- `url`：论文页面；
- `tags`：固定为两个标签，依次为来源（source）和主题（topic）。

页面只展示文章题目、收录日期和标签，不显示文章介绍。

提交到 `main` 分支后，GitHub Actions 会自动重新发布网站。

## 本地预览

```bash
npm install
npm run dev
```

## 构建检查

```bash
npm run build
```
