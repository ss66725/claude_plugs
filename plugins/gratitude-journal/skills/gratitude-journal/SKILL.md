---
name: gratitude-journal
description: 幸福课 · 三件好事练习：每天一份 Markdown，记三件让自己感到幸运或开心的事，可选写「为什么」，并查看最近几天的连续天数。当用户说记三件好事、今天有什么开心的、或想看最近坚持得怎么样时使用。
---

# 幸福课 · 三件好事

每天一份 Markdown，记三件让自己开心或幸运的事。重点不是写得好，是**每天都写**。

## 三条命令

```bash
# 今天的文件（不存在就按模板建），返回路径和已记几条
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" today

# 记一条，省略 --slot 就填第一个空位；三条满了往后追加
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" add "今天把一个卡了很久的问题解决了" --why "因为终于愿意翻文档了"

# 最近 7 天的情况：每天几条、连续多少天、哪几天空着
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" review --days 7
```

补记昨天：任何子命令都加 `--date 2026-11-09`。

## 数据在哪

```
<dataDir>\2026-11\2026-11-09.md
```

一天一个文件，按月分文件夹，纯 Markdown。`dataDir` 默认 `D:\02ai_practice\幸福课`，用 `--data-dir` 或环境变量 `GRATITUDE_DATA_DIR` 改。

**注意**：记录目录不要提交进任何仓库。

## 怎么陪用户写

1. 先 `today` 看今天记到哪了。
2. 只问一句：「今天有哪三件让你觉得开心或者幸运的事？」
3. 用户说完，逐条复述确认，再逐条 `add` 写入。
4. 最后报 `progress_line` 和连续天数。

不要替用户编内容，也不要一次问三个问题。用户只想写一条也行，不要催。
