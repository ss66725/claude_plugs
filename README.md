# claude_plugs

三个自用的 Claude Code 插件，由 [dsh_plugs](https://github.com/ss66725/dsh_plugs)（DeepSeek Harness 版）改写而来。

| 插件 | 一句话 | 什么时候用 |
|---|---|---|
| [learning-repo-organizer](./plugins/learning-repo-organizer) | 整理 C / Python / Arduino 学习仓库 | 今天写了一堆练习，想按日期归档、补期望输出、查隐私、再推 GitHub |
| [office-archive](./plugins/office-archive) | 把散落的 Office 文件收进归档库，先出方案再动手 | 下载目录、桌面堆着一堆 Word/Excel/PPT，想按「课程作业 / 课程资料 / 电子书」归位 |
| [gratitude-journal](./plugins/gratitude-journal) | 每天一份 Markdown，记三件让自己开心的事 | 想做「三件好事」练习，但总忘记写 |

三个插件互不依赖，可以只装一个。

---

## 一、安装

在 Claude Code（CLI / 桌面端）里执行：

```
/plugin marketplace add ss66725/claude_plugs
```

然后安装想要的插件：

```
/plugin install learning-repo-organizer@claude_plugs
/plugin install office-archive@claude_plugs
/plugin install gratitude-journal@claude_plugs
```

装完在 `/plugin` 面板里能看到并启用。本地开发时也可以直接把仓库路径当 marketplace：

```
/plugin marketplace add D:\02_AI\01Claude code\claude_plugs
```

## 二、和 dsh_plugs 的对应关系

| dsh_plugs | claude_plugs | 变化 |
|---|---|---|
| `learning_repo_status` 工具 | `scripts/learning_repo.py status` | 逻辑重写为 Python，输出格式一致 |
| `learning_repo_run_tests` 工具 | `scripts/learning_repo.py tests` | 测试规则与 `run_tests.py` 完全一致 |
| `office_archive_plan` / `_apply` | `scripts/office_archive.py plan/apply` | 安全边界保留：方案 6 小时有效、必须 `--confirm`、SHA256 校验 |
| `gratitude_today/add/review` | `scripts/gratitude.py today/add/review` | 模板、编号规则、连续天数算法一致 |
| 设置页卡片、状态行、`/learnrepo/api` | 无 | Claude 插件没有这些挂载点，砍掉 |
| 内嵌技能 | `skills/<name>/SKILL.md` | 原样保留，改了提交署名与脚本路径 |

技能正文里的 `${CLAUDE_PLUGIN_ROOT}` 会被替换成插件目录的绝对路径，所以脚本不用写死位置。

## 三、学习仓库插件怎么用

三条命令，都是只读：

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" status
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" status --repo c --tests
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" tests --repo python --filter 261108
```

仓库路径写在脚本顶部的 `DEFAULT_REPOS`：

| id | 路径 | GitHub |
|---|---|---|
| `c` | `D:\01_代码\01c` | ss66725/C |
| `python` | `D:\01_代码\01py` | ss66725/Python |
| `arduino` | `D:\01_代码\01arduino\coding` | ss66725/Arduino |

要改路径：编辑 `DEFAULT_REPOS`，或用 `--config repos.json` 传一份自己的配置。

对话里直接说「看看我的学习仓库现在什么状态」「把 C 仓库的测试跑一下」「帮我整理今天的练习」，技能会自己调用。

## 四、Office 归档插件怎么用

**规划与执行是分开的**：`plan` 只读、只出方案；`apply` 必须带 `--confirm`，方案 6 小时内有效。

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/office_archive.py" plan \
  --source "D:\下载\待整理" --target "D:\归档"
```

看过方案再执行：

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/office_archive.py" apply \
  --plan-id <方案 id> --target "D:\归档" --confirm --mode copy
```

`--source` 与 `--target` 相同表示**原地整理**：只处理还散落在根目录和 `99_未归类/` 的文件，强制 `move`。

归档后在 `00_索引/` 下生成：`文件索引.csv`、`文件索引.md`、`迁移清单.csv`、`归档日志.jsonl`、`还原到原位置.ps1`。

分类规则按顺序匹配、第一条命中生效，用 `--rules rules.json` 替换内置规则：

```json
[{ "match": ["实验报告", "课程笔记"], "dir": "01_课程作业/程序设计实验", "note": "实验报告" }]
```

## 五、幸福课插件怎么用

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" today
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" add "今天把卡了很久的问题解决了" --why "终于愿意翻文档"
python "${CLAUDE_PLUGIN_ROOT}/scripts/gratitude.py" review --days 7
```

数据默认在 `D:\02ai_practice\幸福课`，一天一个文件、按月分文件夹：`2026-11\2026-11-10.md`。用 `--data-dir` 或 `GRATITUDE_DATA_DIR` 改。

**记录目录不要提交进仓库。**

## 六、目录结构

```
claude_plugs/
├── .claude-plugin/marketplace.json     市场清单，三个插件都在这登记
├── plugins/
│   ├── learning-repo-organizer/
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/learning-repo-organizer/
│   │   │   ├── SKILL.md                 整理流程
│   │   │   ├── references/              c.md / python.md / arduino.md
│   │   │   └── scripts/run_tests.py     统一测试运行器（复制到仓库根目录用）
│   │   ├── scripts/learning_repo.py     盘点 + 测试
│   │   └── commands/                    /status、/test
│   ├── office-archive/
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/office-archive/SKILL.md
│   │   ├── scripts/office_archive.py
│   │   └── commands/plan.md
│   └── gratitude-journal/
│       ├── .claude-plugin/plugin.json
│       ├── skills/gratitude-journal/SKILL.md
│       ├── scripts/gratitude.py
│       └── commands/log.md
├── LICENSE
└── README.md
```

环境要求：Python ≥ 3.10；跑 C 测试需要 `gcc`（w64devkit 的即可）。

# 许可

MIT，见 [LICENSE](./LICENSE)。
