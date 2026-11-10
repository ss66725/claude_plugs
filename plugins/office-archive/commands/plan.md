---
description: 扫描目录并生成 Office 归档方案（只读，不动文件）
argument-hint: "<源目录> <归档目录>"
allowed-tools: Bash
---

生成一份归档方案，不移动、不复制任何文件。

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/office_archive.py" plan --source $1 --target $2
```

如果用户只给了一个目录（`$1` 与 `$2` 相同，或只给了 `$1`），那就是原地整理：

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/office_archive.py" plan --source $1 --target $1
```

把方案原样讲给用户：多少个文件、分到哪些目录、有没有重名或内容重复、几个未命中规则。**然后停下等用户确认**，不要自己执行 apply。
