#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把三个学习仓库的进度同步到个人主页 README（ss66725/ss66725）。

    python update_profile.py --repo-dir "D:\\02ai_practice\\ss66725"
    python update_profile.py --repo-dir "D:\\02ai_practice\\ss66725" --push

只改 README 里两个标记之间的内容，标记以外的文字一个字都不动：

    <!-- profile-auto:start -->
    ...这里由脚本重写...
    <!-- profile-auto:end -->

有变化才写文件；加了 --push 才提交推送（git 已配置 GitHub 专用代理）。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_REPOS = [
    {"id": "c", "label": "C", "path": r"D:\01_代码\01c", "remote": "https://github.com/ss66725/C"},
    {"id": "python", "label": "Python", "path": r"D:\01_代码\01py", "remote": "https://github.com/ss66725/Python"},
    {"id": "arduino", "label": "Arduino", "path": r"D:\01_代码\01arduino\coding", "remote": "https://github.com/ss66725/Arduino"},
]

CODE_EXT = {".c", ".h", ".py", ".ino"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".vscode", ".idea", "build"}

START = "<!-- profile-auto:start -->"
END = "<!-- profile-auto:end -->"


def scan(repo: dict) -> dict:
    root = Path(repo["path"])
    info = {"label": repo["label"], "remote": repo["remote"], "exists": root.is_dir(),
            "folders": 0, "programs": 0, "tests": 0, "latest": None}
    if not info["exists"]:
        return info

    latest = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_parts = Path(dirpath).relative_to(root).parts
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        if len(rel_parts) == 0:
            info["folders"] = len(dirnames)
        for name in filenames:
            full = Path(dirpath) / name
            suffix = full.suffix.lower()
            if suffix in CODE_EXT:
                info["programs"] += 1
                try:
                    latest = max(latest, full.stat().st_mtime)
                except OSError:
                    pass
            elif suffix == ".txt" and rel_parts and rel_parts[-1] == "tests":
                info["tests"] += 1
    info["latest"] = datetime.fromtimestamp(latest).strftime("%Y-%m-%d") if latest else "—"
    return info


def build_block(scans: list[dict]) -> str:
    dated = [scan["latest"] for scan in scans if scan["latest"] and scan["latest"] != "—"]
    newest = max(dated) if dated else "—"
    lines = [
        START,
        f"最近一次更新：**{newest}**",
        "",
        "| 仓库 | 最近更新 | 日期文件夹 | 程序 | 其中可自动测试 |",
        "|---|---|---|---|---|",
    ]
    for scan in scans:
        name = f"[{scan['label']}]({scan['remote']})"
        if not scan["exists"]:
            lines.append(f"| {name} | 路径不存在 | — | — | — |")
            continue
        tests = scan["tests"] if scan["tests"] else "—"
        lines.append(
            f"| {name} | {scan['latest']} | {scan['folders']} | {scan['programs']} | {tests} |"
        )
    lines.append(END)
    return "\n".join(lines)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="同步学习进度到个人主页 README")
    parser.add_argument("--repo-dir", required=True, help="ss66725/ss66725 的本地克隆目录")
    parser.add_argument("--push", action="store_true", help="有变化时提交并推送")
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir)
    readme = repo_dir / "README.md"
    if not readme.exists():
        raise SystemExit(f"找不到 {readme}，先 clone ss66725/ss66725")

    text = readme.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"README 里缺少标记 {START} / {END}，先在文件里加上这两行")
    if text.index(START) > text.index(END):
        raise SystemExit("标记顺序不对：start 必须在 end 前面")

    scans = [scan(repo) for repo in DEFAULT_REPOS]
    block = build_block(scans)
    updated = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _match: block,
        text,
        count=1,
        flags=re.DOTALL,
    )

    if updated == text:
        print("主页已经是最近状态，不需要改动。")
        return

    readme.write_text(updated, encoding="utf-8", newline="\n")
    print("已更新 README 的进度区：")
    print(block)

    if not args.push:
        print("\n（没有加 --push，只改了本地文件）")
        return

    def git(*argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(repo_dir), *argv], capture_output=True, text=True, encoding="utf-8", errors="replace")

    git("add", "README.md")
    commit = git("commit", "-m", "更新学习进度（自动）\n\nCo-Authored-By: Claude Code <noreply@anthropic.com>")
    if commit.returncode != 0:
        print("提交失败：\n" + (commit.stderr or commit.stdout))
        raise SystemExit(1)
    push = git("push", "origin", "HEAD")
    if push.returncode != 0:
        print("推送失败，错误原文：\n" + (push.stderr or push.stdout))
        raise SystemExit(1)
    print("已提交并推送。")


if __name__ == "__main__":
    main()
