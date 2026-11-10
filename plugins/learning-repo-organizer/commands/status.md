---
description: 只读盘点学习仓库（C / Python / Arduino），不修改任何文件
argument-hint: "[c|python|arduino] [--tests]"
allowed-tools: Bash
---

对三个学习仓库做一次只读盘点。参数是可选的仓库名和 `--tests`：

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" status $ARGUMENTS
```

把脚本输出整理成中文汇报给用户：

- 每个仓库一行：文件数、日期文件夹、测试文件数、最近改动
- 隐私检查命中要单独列出来，并说明是真凭据还是代码里的变量名
- 如果用户加了 `--tests`，把 PASS / FAIL 统计写清楚，失败的用例名单独列出

只读操作：不要修改文件，不要提交，不要推送。
