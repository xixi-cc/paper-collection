# Xixi's Paper Collection

一个可搜索、可筛选的个人论文收藏站，部署在 GitHub Pages。

## 添加文章

编辑 `public/papers.json`，复制一条现有记录并修改内容。每条记录包含：

- `id`：稳定且唯一的标识，arXiv 文章建议直接使用 arXiv ID；
- `date`：收录日期，格式为 `YYYY-MM-DD`；
- `title` / `titleZh`：英文与中文标题；
- `url`：论文页面；
- `note`：你为什么收藏它、最值得记住的结论；
- `details`：作者、机构或其他可搜索信息；
- `readingMinutes`：预计阅读时间；
- `tags`：来源、月份和主题标签。

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
