---
description: 记今天的第 N 件好事
argument-hint: "<一条好事> [--why 为什么]"
allowed-tools: Bash
---

先看今天记到哪了：

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" today
```

再写入用户说的这一条：

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" add $ARGUMENTS
```

写入后只报一句进度（已记 N/3）和连续天数，不要长篇总结。
