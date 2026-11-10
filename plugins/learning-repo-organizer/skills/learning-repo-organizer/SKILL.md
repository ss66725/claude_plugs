---
name: learning-repo-organizer
description: 整理学习代码仓库（C、Python、Arduino）。按日期归档练习，为每天写 README 和根目录索引，为能自动运行的程序补充期望输出（tests/），检查隐私文件，更新 .gitignore，并提交推送到 GitHub。当用户要整理学习仓库、归档今天的练习、补充期望输出、或把本地代码提交到学习仓库时使用。
---

# 学习仓库整理

## 适用范围

仓库类型由文件判断：`.c` 是 C，`.py` 是 Python，`.ino` 是 Arduino。语言相关的细节见 `references/` 下对应的文件。

## 固定路径

以下路径已经确定，直接使用，不需要每次询问：

| 项目 | 本地路径 | GitHub 仓库 |
|---|---|---|
| C 语言 | `D:\01_代码\01c` | https://github.com/ss66725/C |
| Python | `D:\01_代码\01py` | https://github.com/ss66725/Python |
| Arduino | `D:\01_代码\01arduino\coding` | https://github.com/ss66725/Arduino |
| 个人主页 | — | https://github.com/ss66725/ss66725 |

- Arduino 的 `D:\01_代码\01arduino\libraries` 和 CH340 驱动不属于仓库，不上传，也不删除。
- 原 `D:\summer_practice` 已并入 Python 仓库（最后提交 `a6d7153`），原目录隔离在
  `D:\99_归档\_待删_2026-11-09\summer_practice`，不再作为来源目录。
- 代理：`127.0.0.1:10808`。只在用户开着代理时使用。

## 工作流程

按顺序做，每一步都要确认结果，再进入下一步。

1. **确认范围**：仓库和路径已在“固定路径”中写明，直接使用。只需确认日期（默认今天，格式 YYMMDD）以及其他不确定的选择，例如文件夹命名、是否删除文件、是否提交。
2. **盘点**：列出所有文件和修改日期，查看 `git status`。用 `git ls-remote` 检查远程是否已有内容。远程已有内容时，先 `fetch` 再接在它的历史后面，不要覆盖。
3. **归档**：把新文件放进日期文件夹（YYMMDD）。按修改日期分组时，每个日期一个文件夹。保持原文件名和文件夹名，除非用户同意改名。已被 git 跟踪的文件用 `git mv` 改名。
4. **清理**：删除临时文件或编译产物之前，先看内容，列出清单，等用户确认。作业和用户的练习文件不删除。第三方库和驱动不删除。
5. **README**：每个日期文件夹有一个 README，包括：文件表（文件、内容）、知识点、本次改动、期望输出说明。根目录 README 列出所有文件夹，并链接到各自的 README。
6. **期望输出**：能自动运行的程序，在同级的 `tests/` 文件夹里写 `<程序名>.txt`，格式见 `scripts/run_tests.py` 顶部的说明。输入要保证程序能正常结束，避免等待输入时出现 EOF 或死循环。随机、画图、联网、硬件相关的程序不写期望输出，并在 README 里说明原因。运行 `python run_tests.py`，全部 PASS 才算完成。
7. **隐私检查**：搜索 `cookie`、`password`、`passwd`、`ssid`、`token`、`secret`、`api key`。发现真实的凭据或个人信息时，停止并告诉用户。`YOUR_COOKIE_HERE` 这类占位符可以保留。
8. **.gitignore**：按语言补充忽略规则，见 `references/`。
9. **修改源码**：只修复明确的错误，例如编译错误、明显的逻辑错误、可能的缓冲区溢出。风格、警告和设计问题只列出来，由用户决定是否修改。修改前要说明改了什么。
10. **提交推送**：先征求同意。用户明确说“提交推送”后再做。提交信息要写清楚改动，并以 `Co-Authored-By: Claude Code <noreply@anthropic.com>` 结尾。如果用户开着代理，推送时加上代理设置（见“固定路径”）。推送后用 `git ls-remote` 确认远程 HEAD 与本地一致。

## 插件自带工具

插件里有两条现成的脚本，不用自己拼命令：

```bash
# 盘点三个仓库（只读）：文件数、日期文件夹、测试文件、最近改动、隐私命中
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" status

# 只盘点 C 仓库，顺带跑测试
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" status --repo c --tests

# 跑某个仓库的测试，可只跑某天
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" tests --repo python --filter 261108

# 机器可读的输出
python "${CLAUDE_PLUGIN_ROOT}/scripts/learning_repo.py" status --json
```

`status` 和 `tests` 都是只读的，不改文件、不提交。仓库路径写在脚本顶部的 `DEFAULT_REPOS` 里，也可以用 `--config` 传一个 JSON 覆盖。测试规则和 `scripts/run_tests.py` 完全一致。

## 常见问题

- **推送时连接被重置**：重试几次。确认代理是否开着。
- **中文显示乱码**：文件用 UTF-8 保存即可。乱码通常是终端的编码设置造成的，不影响文件内容。
- **文件名里有 `%` 或空格**：改名，或在命令里加引号。
- **运行测试时集合顺序不固定**：运行器已经设置 `PYTHONHASHSEED=0`，直接用 `run_tests.py` 即可。

## 参考文件

- `references/c.md`：C 语言的编译、测试和忽略规则
- `references/python.md`：Python 的测试、忽略规则和隐私要点
- `references/arduino.md`：Arduino 的文档写法、第三方库和隐私要点
- `scripts/run_tests.py`：统一的测试运行器，复制到仓库根目录即可使用
