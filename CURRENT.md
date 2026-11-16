# Paper Collection 当前发布入口

2026-11-16：按用户交回的删除选择清单移除117条目录记录，1003→886。

- 输入：`paper-collection-delete-2026-11-16-117.json`，SHA-256 `9be0b561bcb4815b1447a3b0159b45a6008cfbb66197a20eaed9f892a35a1b11`。
- 117个唯一ID、题目和URL均与清单固定的发布快照逐项一致；保留条目内容和顺序不变。
- `data/collection-removals.json` 保留明确排除项；构建会阻止旧目录重新引入。
- 此次范围是Paper Collection目录及RSS；独立Daily/Paper Card站点与科学评级历史记录保留。
- 私有删除证据和发布回执位于canonical网站工作区 `local-state/collection-delete-evidence-20261116/`；以回执的部署与线上读回结果确定实际发布完成。
- 后续目录导入/评级同步必须从最新origin/main出发并保留排除项，不可覆盖回旧1003篇目录。
