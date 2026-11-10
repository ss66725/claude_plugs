#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学习仓库工具（Claude 插件版）

三个子命令，对应 DSH 插件里的 learning_repo_status / learning_repo_run_tests 两个工具：

    python learning_repo.py repos
    python learning_repo.py status [--repo c] [--tests] [--limit 40] [--json]
    python learning_repo.py tests  --repo c [--filter 261108] [--limit 40] [--json]

路径默认写在 DEFAULT_REPOS 里；要改就改这里，或用 --config 指向一个 JSON：

    {"repositories": [{"id": "c", "label": "C", "path": "D:\\\\...", "remote": "...", "languages": ["c"]}]}

规则与仓库里的 run_tests.py 一致：
  - C：gcc -std=c11 -Wall -Wextra -lm
  - Python：PYTHONHASHSEED=0、PYTHONIOENCODING=utf-8、-X utf8
  - 行尾空白统一去掉，首尾空行忽略
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 配置：三个学习仓库
# ---------------------------------------------------------------------------

DEFAULT_REPOS = [
    {
        "id": "c",
        "label": "C",
        "path": r"D:\01_代码\01c",
        "remote": "https://github.com/ss66725/C",
        "languages": ["c"],
    },
    {
        "id": "python",
        "label": "Python",
        "path": r"D:\01_代码\01py",
        "remote": "https://github.com/ss66725/Python",
        "languages": ["python"],
    },
    {
        "id": "arduino",
        "label": "Arduino",
        "path": r"D:\01_代码\01arduino\coding",
        "remote": "https://github.com/ss66725/Arduino",
        "languages": ["arduino"],
    },
]

DEFAULT_TEST_TIMEOUT_MS = 30000

# ---------------------------------------------------------------------------
# 扫描规则
# ---------------------------------------------------------------------------

LANG_BY_EXT = {"c": "c", "h": "c", "py": "python", "ino": "arduino"}

SKIP_NAMES = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", "build", ".pio",
}

SKIP_EXT = {
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "ico", "pdf", "zip", "7z", "rar", "gz",
    "exe", "dll", "o", "obj", "a", "lib", "pyc", "class", "jar", "mp3", "mp4", "wav",
    "xlsx", "xls", "doc", "docx", "ppt", "pptx", "ttf", "otf", "woff", "woff2",
}

TEXT_EXT = {"c", "h", "py", "ino", "txt", "md", "json", "js", "ts", "env", "yml", "yaml", "ini", "cfg", "conf"}

_ASSIGN = r"\s*[:=(]\s*"
_QUOTED = r"(['\"]?)([^'\"\s]{6,})\1"

PRIVACY_RULES = [
    # Arduino / Python 里常见 WiFi_SSID 这类标识符，所以 ssid 匹配后缀而不是词边界
    ("ssid", re.compile(
        r"(?:^|[^A-Za-z0-9])[A-Za-z0-9_]*(?:ssid|wifi_?name|wifi_?ssid)"
        + _ASSIGN + r"(['\"]?)([^'\"\s,;}{]{1,64})\1",
        re.IGNORECASE | re.MULTILINE)),
    ("wifiPassword", re.compile(
        r"[A-Za-z0-9_]{0,24}(?:pass(?:word|wd)?|pwd)" + _ASSIGN + _QUOTED,
        re.IGNORECASE)),
    ("apiKey", re.compile(
        r"[A-Za-z0-9_]{0,16}(?:api[_-]?key|apikey)" + _ASSIGN + _QUOTED,
        re.IGNORECASE)),
    ("cookie", re.compile(
        r"[A-Za-z0-9_]{0,16}cookie" + _ASSIGN + _QUOTED, re.IGNORECASE)),
    ("token", re.compile(
        r"[A-Za-z0-9_]{0,16}token" + _ASSIGN + _QUOTED, re.IGNORECASE)),
    ("secret", re.compile(
        r"[A-Za-z0-9_]{0,16}secret" + _ASSIGN + _QUOTED, re.IGNORECASE)),
    ("credential", re.compile(
        r"[A-Za-z0-9_]{0,16}credential" + _ASSIGN + _QUOTED, re.IGNORECASE)),
]

PLACEHOLDER = re.compile(
    r"^(your[_<]|xxx+[<]?$|[<{[$]|\.\.\.|changeme|replace|todo|placeholder|example"
    r"|none|null|undefined|nil|true|false|input|str\(|os\.|getenv|environ|\*+$)",
    re.IGNORECASE,
)

MAX_FILES = 20000
MAX_PRIVACY_HITS = 25
MAX_RECORDED_FILES = 60


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def load_repositories(config_path: str | None) -> list[dict]:
    raw = None
    if config_path:
        raw = json.loads(Path(config_path).read_text(encoding="utf-8"))
    elif os.environ.get("LEARNING_REPO_CONFIG"):
        raw = json.loads(Path(os.environ["LEARNING_REPO_CONFIG"]).read_text(encoding="utf-8"))
    if raw is None:
        return [dict(repo) for repo in DEFAULT_REPOS]

    repos = []
    for index, entry in enumerate(raw.get("repositories") or []):
        if not isinstance(entry, dict) or not str(entry.get("path") or "").strip():
            continue
        repo_id = str(entry.get("id") or f"repo-{index + 1}").strip()
        repos.append({
            "id": repo_id,
            "label": str(entry.get("label") or repo_id),
            "path": str(Path(entry["path"]).resolve()),
            "remote": str(entry.get("remote") or ""),
            "languages": [str(item) for item in (entry.get("languages") or [])],
        })
    return repos


def pick_repository(repos: list[dict], query: str | None) -> list[dict]:
    if not query:
        return repos
    needle = query.strip().lower()
    for repo in repos:
        if needle in {repo["id"].lower(), repo["label"].lower()}:
            return [repo]
    known = "、".join(repo["id"] for repo in repos)
    raise SystemExit(f"Unknown repository: {query}（当前配置：{known}）")


def language_of(name: str) -> str | None:
    dot = name.rfind(".")
    if dot < 0:
        return None
    return LANG_BY_EXT.get(name[dot + 1:].lower())


def is_skipped(name: str) -> bool:
    lower = name.lower()
    if lower in SKIP_NAMES:
        return True
    dot = lower.rfind(".")
    return dot >= 0 and lower[dot + 1:] in SKIP_EXT


def read_text_head(path: Path, limit: int = 120000) -> str:
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit)
    except OSError:
        return ""
    if b"\x00" in data:
        return ""
    return data.decode("utf-8", errors="replace")


def is_placeholder(value: str) -> bool:
    trimmed = value.strip().strip("\"'`")
    if trimmed == "":
        return True
    # secret = rand() 这类是函数调用，不是凭据
    if re.match(r"^[A-Za-z_][\w.]*\(", trimmed):
        return True
    return PLACEHOLDER.search(trimmed) is not None


def scan_text_for_privacy(text: str) -> list[dict]:
    hits: list[dict] = []
    for rule_id, pattern in PRIVACY_RULES:
        for match in pattern.finditer(text):
            value = match.group(2) or ""
            if is_placeholder(value):
                continue
            line = text.count("\n", 0, match.start()) + 1
            hits.append({
                "rule": rule_id,
                "line": line,
                "value": value if len(value) <= 40 else value[:40] + "…",
            })
            if len(hits) >= MAX_PRIVACY_HITS:
                return hits
    return hits


def git_branch(root: Path) -> str | None:
    try:
        text = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        return text[5:] if text.startswith("ref: ") else text
    except OSError:
        return None


def git_tracked_count(root: Path) -> int:
    try:
        with open(root / ".git" / "index", "rb") as handle:
            head = handle.read(12)
        return max(0, int.from_bytes(head[8:12], "big") - 1)
    except OSError:
        return 0


def program_folder_of(test_file: Path) -> Path:
    """tests/ 的上一级就是程序所在目录。"""
    return test_file.parent.parent


# ---------------------------------------------------------------------------
# 扫描一个仓库
# ---------------------------------------------------------------------------

def scan_repository(repo: dict) -> dict:
    root = Path(repo["path"])
    result = {
        "id": repo["id"],
        "label": repo["label"],
        "path": str(root),
        "remote": repo.get("remote", ""),
        "exists": False,
        "isGit": False,
        "branch": None,
        "fileCount": 0,
        "languageCounts": {},
        "languages": [],
        "dayFolders": [],
        "testFiles": 0,
        "testsWithoutProgram": 0,
        "latest": None,
        "files": [],
        "privacyHits": [],
        "tracked": 0,
        "truncated": False,
        "error": None,
    }
    if not root.exists():
        result["error"] = "missing"
        return result
    if not root.is_dir():
        result["error"] = "not-a-directory"
        return result

    result["exists"] = True
    result["isGit"] = (root / ".git").is_dir()
    result["branch"] = git_branch(root) if result["isGit"] else None

    known = set(repo.get("languages") or LANG_BY_EXT.values())
    day_folders: set[str] = set()
    languages: set[str] = set()
    language_counts: dict[str, int] = {}
    files: list[dict] = []
    test_entries: list[dict] = []
    visited = 0
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [
            name for name in sorted(dirnames)
            if not (name.startswith(".") and name not in {".gitignore", ".gitattributes"})
            and not is_skipped(name)
        ]
        for name in dirnames:
            if here == root and re.fullmatch(r"\d{6}", name):
                day_folders.add(name)

        for name in sorted(filenames):
            if name.startswith(".") and name not in {".gitignore", ".gitattributes"}:
                continue
            if is_skipped(name):
                continue
            full = here / name
            rel = full.relative_to(root).as_posix()
            depth = len(rel.split("/"))
            language = language_of(name)
            parent_is_tests = depth >= 2 and rel.split("/")[depth - 2] == "tests"
            is_test_file = depth >= 2 and parent_is_tests and name.endswith(".txt")
            is_code = language is not None and language in known
            if not is_code and not is_test_file:
                continue

            visited += 1
            if visited > MAX_FILES:
                truncated = True
                break

            try:
                mtime = full.stat().st_mtime
            except OSError:
                continue

            if is_code:
                languages.add(language)
                language_counts[language] = language_counts.get(language, 0) + 1
                files.append({"path": rel, "name": name, "language": language, "mtime": mtime, "full": full})

            if is_test_file:
                stem = name[:-4]
                folder = program_folder_of(full)
                has_program = any((folder / f"{stem}{ext}").exists() for ext in (".c", ".py", ".ino"))
                test_entries.append({"path": rel, "program": has_program})
        if truncated:
            break

    files.sort(key=lambda item: item["mtime"], reverse=True)
    latest = None
    if files:
        latest = {"path": files[0]["path"], "name": files[0]["name"], "mtime": files[0]["mtime"]}

    privacy_hits: list[dict] = []
    for record in files[:400]:
        extension = record["name"].rsplit(".", 1)[-1].lower()
        if extension not in TEXT_EXT:
            continue
        text = read_text_head(record["full"])
        if not text:
            continue
        for hit in scan_text_for_privacy(text):
            privacy_hits.append({"path": record["path"], **hit})
        if len(privacy_hits) >= MAX_PRIVACY_HITS:
            break

    result.update({
        "fileCount": len(files),
        "languageCounts": language_counts,
        "languages": sorted(languages),
        "dayFolders": sorted(day_folders, reverse=True)[:40],
        "testFiles": len(test_entries),
        "testsWithoutProgram": sum(1 for entry in test_entries if not entry["program"]),
        "latest": latest,
        "files": [
            {"path": item["path"], "language": item["language"], "mtime": item["mtime"]}
            for item in files[:12]
        ],
        "privacyHits": privacy_hits,
        "tracked": git_tracked_count(root) if result["isGit"] else 0,
        "truncated": truncated,
    })
    return result


# ---------------------------------------------------------------------------
# 测试运行
# ---------------------------------------------------------------------------

def parse_cases(text: str) -> list[dict]:
    cases: list[dict] = []
    current: dict | None = None
    section: str | None = None
    for line in text.splitlines():
        if line == "input:":
            if current is not None:
                cases.append(current)
            current = {"input": [], "output": []}
            section = "input"
        elif line == "output:":
            section = "output"
        elif line == "---":
            section = None
        elif current is not None and section is not None:
            current[section].append(line)
    if current is not None:
        cases.append(current)
    return cases


def normalize_output(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def list_test_files(root: Path, prefix: str) -> list[dict]:
    found: list[dict] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [name for name in dirnames if name != ".git" and not is_skipped(name)]
        if Path(dirpath).name != "tests":
            continue
        for name in sorted(os.listdir(dirpath)):
            path = Path(dirpath) / name
            if not path.is_file() or not name.endswith(".txt"):
                continue
            rel = path.relative_to(root).as_posix()
            if prefix and not rel.startswith(prefix):
                continue
            folder = program_folder_of(path)
            stem = name[:-4]
            program = next(
                (folder / f"{stem}{ext}" for ext in (".c", ".py", ".ino") if (folder / f"{stem}{ext}").exists()),
                None,
            )
            found.append({"rel": rel, "file": path, "program": program})
    return sorted(found, key=lambda item: item["rel"])


def run_process(argv: list[str], cwd: Path, stdin_text: str, timeout_s: float) -> dict:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        return {
            "exitCode": completed.returncode,
            "timedOut": False,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "exitCode": None,
            "timedOut": True,
            "stdout": (error.stdout or "") if isinstance(error.stdout, str) else "",
            "stderr": (error.stderr or "") if isinstance(error.stderr, str) else "",
        }
    except OSError as error:
        return {"exitCode": 1, "timedOut": False, "stdout": "", "stderr": str(error)}


def run_repository_tests(repo: dict, prefix: str = "", limit: int = 40, timeout_ms: int = DEFAULT_TEST_TIMEOUT_MS) -> dict:
    root = Path(repo["path"])
    limit = max(1, min(int(limit or 40), 200))
    timeout_s = max(1.0, min(int(timeout_ms or DEFAULT_TEST_TIMEOUT_MS), 300000) / 1000.0)

    result = {
        "repository": repo["id"],
        "label": repo["label"],
        "path": str(root),
        "status": "passed",
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "cases": [],
        "summary": "",
    }
    if not root.is_dir():
        result["status"] = "missing"
        return result

    test_files = list_test_files(root, prefix)
    if not test_files:
        result["summary"] = f"{repo['label']}: 没有找到测试文件"
        return result

    cases = result["cases"]
    with tempfile.TemporaryDirectory(prefix="claude-learnrepo-") as work_dir:
        for entry in test_files:
            if len(cases) >= limit:
                result["skipped"] += 1
                continue
            if entry["program"] is None:
                cases.append({"test": entry["rel"], "status": "skip", "reason": "no matching program"})
                result["skipped"] += 1
                continue

            try:
                text = entry["file"].read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                cases.append({"test": entry["rel"], "status": "fail", "reason": str(error)})
                result["failed"] += 1
                continue

            parsed = parse_cases(text)
            program: Path = entry["program"]
            command: list[str]
            env = dict(os.environ)

            if program.suffix == ".c":
                safe_name = f"{repo['id']}-{re.sub(r'[^A-Za-z0-9]+', '_', entry['rel'])}.exe"
                exe = Path(work_dir) / safe_name
                compiled = run_process(
                    ["gcc", "-std=c11", "-Wall", "-Wextra", "-o", str(exe), str(program), "-lm"],
                    root, "", timeout_s,
                )
                if compiled["timedOut"] or compiled["exitCode"] != 0:
                    cases.append({
                        "test": entry["rel"], "status": "fail", "reason": "compile failed",
                        "actual": compiled["stderr"][:4000],
                    })
                    result["failed"] += max(1, len(parsed))
                    continue
                command = [str(exe)]
            elif program.suffix == ".py":
                env["PYTHONHASHSEED"] = env.get("PYTHONHASHSEED", "0")
                env["PYTHONIOENCODING"] = env.get("PYTHONIOENCODING", "utf-8")
                command = [sys.executable, "-X", "utf8", str(program)]
            else:
                cases.append({"test": entry["rel"], "status": "skip", "reason": "Arduino sketch has no host runner"})
                result["skipped"] += 1
                continue

            for index, test_case in enumerate(parsed, start=1):
                if len(cases) >= limit:
                    result["skipped"] += 1
                    continue
                stdin_text = "\n".join(test_case["input"]) + "\n" if test_case["input"] else ""
                expected = "\n".join(test_case["output"])
                run = run_process(command, root, stdin_text, timeout_s)

                actual = run["stdout"]
                if not run["timedOut"] and run["exitCode"] != 0 and run["stderr"].strip():
                    actual = f"{actual}\n[stderr]\n{run['stderr'][:2000]}"
                if run["timedOut"]:
                    actual = "<timeout>"

                ok = not run["timedOut"] and normalize_output(actual) == normalize_output(expected)
                if ok:
                    result["passed"] += 1
                else:
                    result["failed"] += 1
                cases.append({
                    "test": entry["rel"],
                    "case": index,
                    "program": program.relative_to(root).as_posix(),
                    "status": "pass" if ok else "fail",
                    "expected": expected[:4000],
                    "actual": actual[:4000],
                })

    result["status"] = "failed" if result["failed"] else "passed"
    result["summary"] = (
        f"{result['label']}: {result['passed']} passed, {result['failed']} failed"
        + (f", {result['skipped']} skipped" if result["skipped"] else "")
    )
    return result


def format_test_report(result: dict) -> str:
    lines = [f"{result['label']}: {result['passed']} passed, {result['failed']} failed, {result['skipped']} skipped"]
    for case in result["cases"]:
        name = case["test"] if "case" not in case else f"{case['test']} #{case['case']}"
        if case["status"] == "pass":
            lines.append(f"PASS  {name}")
        elif case["status"] == "skip":
            lines.append(f"SKIP  {name}  ({case.get('reason', '')})")
        else:
            reason = f"  ({case['reason']})" if case.get("reason") else ""
            lines.append(f"FAIL  {name}{reason}")
            if case.get("expected"):
                lines.append(f"      expected: {case['expected']}")
            if case.get("actual"):
                lines.append(f"      actual:   {case['actual']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def human_status(report: dict) -> str:
    lines = [f"扫描时间：{report['scannedAt']}", ""]
    for repo in report["repositories"]:
        head = f"【{repo['label']}】{repo['path']}"
        if repo["error"] == "missing":
            lines.append(head + "  → 目录不存在")
            lines.append("")
            continue
        if repo["error"]:
            lines.append(head + f"  → {repo['error']}")
            lines.append("")
            continue
        langs = "、".join(f"{name} {count}" for name, count in repo["languageCounts"].items()) or "无"
        lines.append(head)
        lines.append(f"  文件 {repo['fileCount']} 个（{langs}）· 日期文件夹 {len(repo['dayFolders'])} 个 · 测试文件 {repo['testFiles']} 个")
        if repo["testsWithoutProgram"]:
            lines.append(f"  有 {repo['testsWithoutProgram']} 个测试文件找不到对应程序")
        if repo["branch"]:
            lines.append(f"  分支 {repo['branch']} · 已跟踪 {repo['tracked']} 个文件")
        if repo["latest"]:
            lines.append(f"  最近改动：{repo['latest']['path']}")
        if repo["dayFolders"]:
            lines.append(f"  最近的日期文件夹：{'、'.join(repo['dayFolders'][:8])}")
        if repo["privacyHits"]:
            lines.append(f"  隐私检查命中 {len(repo['privacyHits'])} 处：")
            for hit in repo["privacyHits"][:10]:
                lines.append(f"    {hit['path']}:{hit['line']}  {hit['rule']} = {hit['value']}")
        else:
            lines.append("  隐私检查：未发现真实凭据")
        if repo.get("tests"):
            lines.append("")
            lines.append("  " + format_test_report(repo["tests"]).replace("\n", "\n  "))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    # Windows 控制台默认 cp936，中文会乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="学习仓库扫描与测试")
    parser.add_argument("--config", help="仓库配置 JSON 的路径")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("repos", help="列出配置的仓库")

    status_parser = sub.add_parser("status", help="扫描仓库（只读）")
    status_parser.add_argument("--repo", help="仓库 id 或 label，省略则全部")
    status_parser.add_argument("--tests", action="store_true", help="顺带跑测试")
    status_parser.add_argument("--limit", type=int, default=40, help="每个仓库最多跑几个用例")
    status_parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TEST_TIMEOUT_MS)
    status_parser.add_argument("--json", action="store_true", help="输出 JSON")

    tests_parser = sub.add_parser("tests", help="运行某个仓库的测试")
    tests_parser.add_argument("--repo", required=True, help="仓库 id 或 label")
    tests_parser.add_argument("--filter", default="", help="只跑路径前缀匹配的用例，如 261108")
    tests_parser.add_argument("--limit", type=int, default=40)
    tests_parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TEST_TIMEOUT_MS)
    tests_parser.add_argument("--json", action="store_true", help="输出 JSON")

    args = parser.parse_args()
    repos = load_repositories(args.config)

    if args.command == "repos":
        for repo in repos:
            print(f"{repo['id']:8} {repo['label']:8} {repo['path']}  {repo['remote']}")
        return

    if args.command == "status":
        selected = pick_repository(repos, args.repo)
        report = {"scannedAt": datetime.now().isoformat(timespec="seconds")}
        entries = []
        for repo in selected:
            scan = scan_repository(repo)
            if args.tests and scan["exists"] and scan["testFiles"] > 0:
                scan["tests"] = run_repository_tests(repo, limit=args.limit, timeout_ms=args.timeout_ms)
            entries.append(scan)
        report["repositories"] = entries
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(human_status(report))
        return

    repo = pick_repository(repos, args.repo)[0]
    result = run_repository_tests(repo, prefix=args.filter.replace("\\", "/"), limit=args.limit, timeout_ms=args.timeout_ms)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_test_report(result))
    raise SystemExit(0 if result["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
