---
description: 跑学习仓库的期望输出测试（tests/ 下的 .txt）
argument-hint: "<c|python|arduino> [日期前缀，如 261108]"
allowed-tools: Bash
---

运行指定仓库的期望输出测试。第一个参数是仓库，第二个是可选的路径前缀（例如只跑某一天）：

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" tests --repo $ARGUMENTS
```

如果脚本报 Unknown repository，说明仓库名写错了，当前配置：`c`、`python`、`arduino`。

汇报时给：通过数 / 失败数 / 跳过数，失败用例的 expected 与 actual 差异。测试规则与仓库里的 `run_tests.py` 一致（C 用 gcc -std=c11 -Wall -Wextra -lm，Python 用 PYTHONHASHSEED=0、PYTHONIOENCODING=utf-8）。
