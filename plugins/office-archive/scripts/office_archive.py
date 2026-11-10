#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Office 文件归档（Claude 插件版）

两步走，规划与执行分开：
    python office_archive.py plan  --source <目录> [--source <目录>] --target <归档库> [--rules rules.json]
    python office_archive.py apply --plan-id <id> --target <归档库> --confirm [--mode copy|move]

设计要点与 DSH 版一致：
  - plan 只读，不动文件；apply 必须带 confirm，且方案 6 小时内有效。
  - copy 保留源文件；move 校验 SHA256 一致后才删源文件。
  - sources 与 target 相同时表示「原地整理」，只处理还没归位的文件，强制 move。
  - 归档后在 00_索引/ 下刷新 文件索引.csv、文件索引.md、迁移清单.csv、归档日志.jsonl、还原到原位置.ps1。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# 默认分类规则：从上往下匹配，第一条命中生效
# ---------------------------------------------------------------------------

DEFAULT_RULES = [
    {"match": ["_tmp_extract"], "dir": "99_待清理/_tmp_extract", "note": "PDF 解包出来的临时图片"},
    {"match": ["方大同", "slide-outline", "标准录音"], "dir": "04_演示文稿/方大同英语课", "note": "英语课 PPT 项目"},
    {"match": ["冰箱不是食品的", "yswg", "ppt题目"], "dir": "04_演示文稿/冰箱冷藏室", "note": "PPT 作业"},
    {"match": ["AI辅助撰写报告文档"], "dir": "04_演示文稿/参考资料", "note": "写报告用的参考资料"},
    {"match": ["资本论"], "dir": "05_电子书", "note": "电子书"},
    {"match": ["实验实训报告"], "dir": "01_课程作业/程序设计实训报告", "note": "程序设计实训报告"},
    {"match": ["产品价格表", "B企业"], "dir": "01_课程作业/表格与图表分析", "note": "表格与图表分析作业"},
    {"match": ["双选会", "大学生涯规划"], "dir": "01_课程作业/就业与生涯规划", "note": "就业指导类作业"},
    {"match": ["读书笔记"], "dir": "01_课程作业", "note": "读书笔记"},
    {"match": ["实验8和9", "课程笔记"], "dir": "02_课程资料/控制系统程序设计基础", "note": "课程笔记与实验题"},
    {"match": ["实训调研报告", "实训报告框架"], "dir": "02_课程资料/实训调研", "note": "实训调研材料"},
    {"match": ["项目计划书"], "dir": "03_项目与方案", "note": "项目计划书"},
]

FALLBACK_DIR = "99_未归类"
MANAGED_RE = re.compile(r"^\d{2}_")
REVISIT_DIR = "99_未归类"
INDEX_DIR = "00_索引"
PLAN_TTL = timedelta(hours=6)

CATEGORY_DESC = {
    "01_课程作业": "平时作业、实训报告、课堂练习",
    "02_课程资料": "课件、课程笔记、实验题、调研材料",
    "03_项目与方案": "项目计划书、方案类文档",
    "04_演示文稿": "PPT 成品及配套讲稿、大纲、素材",
    "05_电子书": "课外阅读电子书",
    "99_待清理": "临时解包产物、中间文件",
    "99_未归类": "没有命中任何规则，需要你补一条规则",
    "（根目录散落）": "还没归位的文件，下次整理会处理",
}

EXT_CN = {
    ".docx": "Word 文档", ".doc": "Word 文档（旧）",
    ".xlsx": "Excel 表格", ".xls": "Excel 表格（旧）",
    ".pptx": "PowerPoint", ".ppt": "PowerPoint（旧）",
    ".pdf": "PDF", ".md": "Markdown", ".txt": "文本", ".csv": "CSV",
    ".png": "图片", ".jpg": "图片", ".jpeg": "图片", ".gif": "图片",
    ".svg": "图片", ".webp": "图片", ".zip": "压缩包",
}


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def pad(n: int) -> str:
    return str(n).zfill(2)


def date_tag(moment: datetime) -> str:
    return f"{str(moment.year)[2:]}{pad(moment.month)}{pad(moment.day)}"


def stamp(moment: datetime) -> str:
    return f"{moment.year}-{pad(moment.month)}-{pad(moment.day)} {pad(moment.hour)}:{pad(moment.minute)}"


def mb(size: int) -> str:
    return f"{size / 1024:.0f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"


def size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size // 1024} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return child.resolve() != parent.resolve()
    except ValueError:
        return False


def same_path(a: Path, b: Path) -> bool:
    return str(a.resolve()).lower() == str(b.resolve()).lower()


def clean_name(name: str) -> str:
    """去掉下载站水印和重复下载留下的 " (1)"，其余名字保持原样。"""
    stem, ext = os.path.splitext(name)
    cleaned = re.sub(r"\s*\(z-lib[^)]*\)", "", stem, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(\d+\)$", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return f"{cleaned or stem}{ext}"


def classify(rel: str, rules: list[dict]) -> tuple[str, str]:
    flat = rel.lower()
    for rule in rules:
        if any(str(key).lower() in flat for key in rule["match"]):
            return rule["dir"], rule.get("note", "")
    return FALLBACK_DIR, "未命中规则"


def walk(root: Path) -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            found.append(Path(dirpath) / name)
    return found


def is_loose(rel: str) -> bool:
    """原地整理：只有「没归位」的文件才算候选。"""
    first = rel.split("/")[0]
    if first == REVISIT_DIR:
        return True
    return MANAGED_RE.match(first) is None


def cat_of(directory: str) -> str:
    if directory in ("", "."):
        return "（根目录散落）"
    return directory.split("/")[0]


def csv_row(cells) -> str:
    import io
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(cells)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def build_plan(sources: list[str], target: str, rules: list[dict]) -> dict:
    target_path = Path(target).resolve()
    entries: list[dict] = []
    warnings: list[str] = []
    by_hash: dict[str, str] = {}
    used_names: set[tuple[str, str]] = set()
    inplace = any(same_path(Path(source), target_path) for source in sources)

    for source in sources:
        abs_source = Path(source).resolve()
        if not abs_source.is_dir():
            warnings.append(f"源目录不存在，已跳过：{source}")
            continue
        self_mode = same_path(abs_source, target_path)
        if not self_mode and is_inside(target_path, abs_source):
            warnings.append(f"归档目录位于源目录内部，已排除：{target_path}")

        for file in walk(abs_source):
            if not self_mode and is_inside(file, target_path):
                continue
            rel = file.relative_to(abs_source).as_posix()
            if self_mode and not is_loose(rel):
                continue
            if self_mode and "/" not in rel and rel.lower() in {"readme.md", "readme.txt"}:
                continue

            try:
                stat = file.stat()
            except OSError:
                continue
            directory, note = classify(rel, rules)

            name = clean_name(file.name)
            tag = date_tag(datetime.fromtimestamp(stat.st_mtime))
            stem, ext = os.path.splitext(name)
            if not stem.startswith(tag) and tag in stem:
                stripped = re.sub(r"\s{2,}", " ", stem.replace(tag, "")).strip()
                if stripped:
                    stem = stripped
            name = f"{stem}{ext}" if stem.startswith(tag) else f"{tag}_{stem}{ext}"

            final = name
            key = (directory.lower(), final.lower())
            if key in used_names:
                stem2, ext2 = os.path.splitext(name)
                i = 2
                while (directory.lower(), f"{stem2} ({i}){ext2}".lower()) in used_names:
                    i += 1
                final = f"{stem2} ({i}){ext2}"
                warnings.append(f"目标重名，已加后缀：{name} → {final}")
            used_names.add((directory.lower(), final.lower()))

            # 原地整理：已经待在正确位置的直接跳过
            if self_mode and same_path(target_path / directory / final, file):
                continue

            sha = hash_file(file)
            duplicate_of = by_hash.get(sha)
            if duplicate_of is None:
                by_hash[sha] = rel

            entries.append({
                "src": str(file),
                "rel": rel,
                "dir": directory,
                "name": final,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size": stat.st_size,
                "sha": sha,
                "note": f"{note}{'；' if note else ''}内容与 {duplicate_of} 完全相同" if duplicate_of else note,
                "duplicateOf": duplicate_of,
            })

    return {
        "id": uuid.uuid4().hex[:8],
        "createdAt": datetime.now().isoformat(),
        "sources": [str(Path(source).resolve()) for source in sources],
        "target": str(target_path),
        "rules": rules,
        "inplace": inplace,
        "entries": entries,
        "warnings": warnings,
    }


def plan_summary(plan: dict) -> str:
    groups: dict[str, list[dict]] = {}
    for entry in plan["entries"]:
        groups.setdefault(entry["dir"], []).append(entry)
    total = sum(entry["size"] for entry in plan["entries"])

    lines = [f"方案 {plan['id']}　·　{len(plan['entries'])} 个文件 / {mb(total)}　·　尚未执行"]
    if plan["inplace"]:
        lines.append(f"原地整理：{plan['target']}（只处理还没归位的文件）")
    else:
        lines.append(f"源目录：{'、'.join(plan['sources'])}")
        lines.append(f"目标：{plan['target']}")
    lines.append("")

    for directory in sorted(groups):
        files = sorted(groups[directory], key=lambda entry: entry["mtime"])
        lines.append(f"{directory}/　（{len(files)} 个，{mb(sum(f['size'] for f in files))}）")
        for entry in files:
            moment = datetime.fromisoformat(entry["mtime"])
            lines.append(f"  {entry['name']}　({pad(moment.month)}-{pad(moment.day)} {pad(moment.hour)}:{pad(moment.minute)})")
        lines.append("")

    if plan["warnings"]:
        lines.append("需要注意：")
        lines.extend(f"- {warning}" for warning in plan["warnings"])
        lines.append("")

    unclassified = sum(1 for entry in plan["entries"] if entry["dir"] == FALLBACK_DIR)
    if unclassified:
        lines.append(f"有 {unclassified} 个文件没有命中规则，会放进 {FALLBACK_DIR}/。补一条规则再重跑会更整齐。")

    lines.append(f'确认无误后执行：office_archive.py apply --plan-id {plan["id"]} --target "{plan["target"]}" --confirm')
    return "\n".join(lines)


def plan_file_path(target: Path, plan_id: str) -> Path:
    return target / INDEX_DIR / ".plans" / f"{plan_id}.json"


def save_plan(plan: dict) -> Path:
    path = plan_file_path(Path(plan["target"]), plan["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def apply_plan(plan: dict, mode: str) -> list[dict]:
    done: list[dict] = []
    target = Path(plan["target"])

    for entry in plan["entries"]:
        directory = target / entry["dir"]
        directory.mkdir(parents=True, exist_ok=True)
        dst = directory / entry["name"]
        src = Path(entry["src"])

        if dst.exists():
            if dst.stat().st_size == entry["size"] and hash_file(dst) == entry["sha"]:
                if mode == "move" and not same_path(src, dst):
                    src.unlink(missing_ok=True)
                done.append({**entry, "dst": str(dst), "status": "already"})
                continue
            stem, ext = os.path.splitext(entry["name"])
            i = 2
            while (directory / f"{stem} ({i}){ext}").exists():
                i += 1
            dst = directory / f"{stem} ({i}){ext}"

        if same_path(src, dst):
            done.append({**entry, "dst": str(dst), "status": "already"})
            continue

        if mode == "move":
            shutil.move(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
            os.utime(dst, (datetime.now().timestamp(), datetime.fromisoformat(entry["mtime"]).timestamp()))

        if hash_file(dst) != entry["sha"]:
            raise SystemExit(f"校验失败，源与副本不一致：{src}")
        done.append({**entry, "dst": str(dst), "status": "moved" if mode == "move" else "copied"})

    write_indexes(done, target)
    return done


# ---------------------------------------------------------------------------
# 索引
# ---------------------------------------------------------------------------

def snapshot(target: Path) -> list[dict]:
    rows: list[dict] = []
    index_dir = target / INDEX_DIR
    for file in walk(target):
        if is_inside(file, index_dir):
            continue
        rel_dir = file.parent.relative_to(target).as_posix()
        if rel_dir == "" and file.name.lower() in {"readme.md", "readme.txt"}:
            continue
        stat = file.stat()
        rows.append({
            "dst": str(file),
            "dir": rel_dir or ".",
            "name": file.name,
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return rows


def append_journal(target: Path, batch: list[dict]) -> None:
    if not batch:
        return
    path = target / INDEX_DIR / "归档日志.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({
            "at": datetime.now().isoformat(),
            "from": entry["src"],
            "to": entry["dst"],
            "status": entry["status"],
        }, ensure_ascii=False)
        for entry in batch
    ]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def write_indexes(done: list[dict], target: Path) -> Path:
    index_dir = target / INDEX_DIR
    index_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()

    moved = [entry for entry in done if entry["status"] != "already"]
    append_journal(target, moved)

    rows = snapshot(target)
    note_of = {entry["dst"]: entry.get("note", "") for entry in done}
    ordered = sorted(rows, key=lambda row: f"{row['dir']}/{row['name']}")

    # 迁移清单（这一批）
    content = "﻿" + csv_row(["原路径", "新路径", "原文件名", "新文件名", "大小(字节)", "修改时间", "SHA256", "分类"])
    for entry in sorted(moved, key=lambda item: item["dst"]):
        content += csv_row([
            entry["src"], entry["dst"], os.path.basename(entry["src"]), os.path.basename(entry["dst"]),
            entry["size"], stamp(datetime.fromisoformat(entry["mtime"])), entry["sha"], entry["dir"],
        ])
    (index_dir / "迁移清单.csv").write_text(content, encoding="utf-8")

    # 文件索引（整库快照）
    content = "﻿" + csv_row(["序号", "大类", "目录", "文件名", "修改日期", "类型", "大小(KB)", "路径", "说明"])
    for i, row in enumerate(ordered, start=1):
        ext = os.path.splitext(row["name"])[1].lower()
        content += csv_row([
            i, cat_of(row["dir"]), row["dir"], row["name"],
            stamp(datetime.fromisoformat(row["mtime"])), EXT_CN.get(ext, "其他"),
            f"{row['size'] / 1024:.1f}", row["dst"], note_of.get(row["dst"], ""),
        ])
    (index_dir / "文件索引.csv").write_text(content, encoding="utf-8")

    # Markdown 索引
    groups: dict[str, list[dict]] = {}
    for row in ordered:
        groups.setdefault(row["dir"], []).append(row)

    lines = [
        "# Office 文件索引",
        "",
        f"生成时间：{stamp(now)}　|　共 {len(ordered)} 个文件、{mb(sum(r['size'] for r in rows))}",
        "",
        "文件名开头的 `YYMMDD_` 是**修改时间**，同一批次的文件会挨在一起。",
        "",
        "## 目录结构",
        "",
        "```",
    ]
    for directory in sorted(groups):
        lines.append("（根目录）" if directory == "." else f"{directory}/")
        for row in sorted(groups[directory], key=lambda item: item["mtime"]):
            lines.append(f"  ├── {row['name']}")
    lines.extend(["```", ""])

    months: dict[str, list[dict]] = {}
    for row in ordered:
        months.setdefault(row["mtime"][:7], []).append(row)
    lines.extend(["## 时间线（按修改时间）", ""])
    for month in sorted(months):
        items = sorted(months[month], key=lambda item: item["mtime"])
        lines.extend([f"### {month}　{len(items)} 个文件", ""])
        for row in items:
            moment = datetime.fromisoformat(row["mtime"])
            where = "（根目录）" if row["dir"] == "." else row["dir"]
            lines.append(f"- `{pad(moment.month)}-{pad(moment.day)} {pad(moment.hour)}:{pad(moment.minute)}`　{row['name']}　—　{where}")
        lines.append("")

    for category in sorted({cat_of(row["dir"]) for row in ordered}):
        items = [row for row in ordered if cat_of(row["dir"]) == category]
        lines.extend([f"## {category}　{len(items)} 个文件", ""])
        if CATEGORY_DESC.get(category):
            lines.extend([f"> {CATEGORY_DESC[category]}", ""])
        lines.append("| 文件 | 修改日期 | 类型 | 大小 | 目录 |")
        lines.append("|---|---|---|---|---|")
        for row in items:
            ext = os.path.splitext(row["name"])[1].lower()
            where = "根目录" if row["dir"] == "." else row["dir"]
            lines.append(
                f"| {row['name']} | {stamp(datetime.fromisoformat(row['mtime']))[:10]} "
                f"| {EXT_CN.get(ext, '其他')} | {size_label(row['size'])} | {where} |"
            )
        lines.append("")
    (index_dir / "文件索引.md").write_text("\n".join(lines), encoding="utf-8")

    # 还原脚本：从归档日志反推
    log_file = index_dir / "归档日志.jsonl"
    latest: dict[str, dict] = {}
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("status") == "moved":
                latest[record["to"]] = record

    ps = [
        "# 还原：把归档里的文件按归档日志复制回最初的位置（归档目录本身保留）",
        "# 用法：powershell -ExecutionPolicy Bypass -File 还原到原位置.ps1",
        "",
        "$ErrorActionPreference = 'Stop'",
        "Write-Host '即将把文件复制回原位置，按 Ctrl+C 可取消…' -ForegroundColor Yellow",
        "Start-Sleep -Seconds 3",
        "$n = 0",
        "",
    ]
    for record in latest.values():
        ps.extend([
            f'if (Test-Path -LiteralPath "{record["to"]}") {{',
            f'  New-Item -ItemType Directory -Path "{os.path.dirname(record["from"])}" -Force | Out-Null',
            f'  Copy-Item -LiteralPath "{record["to"]}" -Destination "{record["from"]}" -Force',
            "  $n++",
            "}",
        ])
    ps.extend(["", 'Write-Host ("已还原 $n 个文件到最初位置") -ForegroundColor Green'])
    (index_dir / "还原到原位置.ps1").write_text("﻿" + "\r\n".join(ps), encoding="utf-8")

    return index_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def command_plan(args) -> int:
    rules = DEFAULT_RULES
    if args.rules:
        rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    if not args.source:
        raise SystemExit("至少要有一个 --source")
    if not args.target:
        raise SystemExit("--target 不能为空")

    plan = build_plan(args.source, args.target, rules)
    if not plan["entries"]:
        message = (
            f"{plan['target']} 里所有文件都已归位。" if plan["inplace"]
            else f"在 {'、'.join(plan['sources'])} 里没有找到任何文件。"
        )
        if plan["warnings"]:
            message += "\n" + "\n".join(plan["warnings"])
        summary = message + f"\n\n方案 {plan['id']} 仍然有效：执行它只会刷新索引，不会移动任何文件。"
    else:
        summary = plan_summary(plan)

    path = save_plan(plan)
    if args.json:
        print(json.dumps({
            "summary": summary,
            "planId": plan["id"],
            "target": plan["target"],
            "inplace": plan["inplace"],
            "total": len(plan["entries"]),
            "bytes": sum(entry["size"] for entry in plan["entries"]),
            "warnings": plan["warnings"],
            "planFile": str(path),
            "groups": [
                {"dir": directory, "count": sum(1 for entry in plan["entries"] if entry["dir"] == directory)}
                for directory in sorted({entry["dir"] for entry in plan["entries"]})
            ],
        }, ensure_ascii=False, indent=2))
    else:
        print(summary)
        print(f"\n方案文件：{path}")
    return 0


def command_apply(args) -> int:
    if not args.confirm:
        raise SystemExit("没有确认就不执行。请先把方案给用户看，得到同意后再加 --confirm。")
    target = Path(args.target).resolve()
    path = plan_file_path(target, args.plan_id)
    if not path.exists():
        raise SystemExit(f"找不到方案 {args.plan_id}，请重新运行 plan。")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("appliedAt"):
        raise SystemExit(f"方案 {args.plan_id} 已于 {plan['appliedAt']} 执行过，请重新生成方案。")
    age = datetime.now() - datetime.fromisoformat(plan["createdAt"])
    if age > PLAN_TTL:
        raise SystemExit("方案已超过 6 小时，文件可能已经变化，请重新生成。")

    mode = "move" if plan["inplace"] else ("move" if args.mode == "move" else "copy")
    done = apply_plan(plan, mode)

    plan["appliedAt"] = datetime.now().isoformat()
    plan["appliedMode"] = mode
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(entry["size"] for entry in done)
    already = sum(1 for entry in done if entry["status"] == "already")
    lines = [
        f"已归档 {len(done)} 个文件 / {mb(total)} → {target}" if done else "没有需要移动的文件，索引已按当前目录刷新。",
        f"方式：{'原地整理（移动）' if plan['inplace'] else ('移动（源文件已删除）' if mode == 'move' else '复制（源文件保留）')}" if done else "",
        f"校验：{len(done)}/{len(done)} SHA256 一致" if done else "",
    ]
    if already:
        lines.append(f"其中 {already} 个此前已归位，内容一致，未重复处理")
    lines.extend([
        "",
        f"索引：{target / INDEX_DIR}",
        "  - 文件索引.csv / 文件索引.md　（整库快照，每次重写）",
        "  - 迁移清单.csv　（这一批的 原位置 → 新位置 + SHA256）",
        "  - 归档日志.jsonl　（累积日志，还原脚本按它生成）",
        "  - 还原到原位置.ps1　（把文件复制回最初位置）",
    ])
    print("\n".join(line for line in lines if line is not None))
    return 0


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Office 文件归档：先出方案，确认后执行")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_parser = sub.add_parser("plan", help="只读扫描，生成归档方案")
    plan_parser.add_argument("--source", action="append", help="要整理的目录，可重复")
    plan_parser.add_argument("--target", required=True, help="归档根目录")
    plan_parser.add_argument("--rules", help="自定义分类规则 JSON")
    plan_parser.add_argument("--json", action="store_true")

    apply_parser = sub.add_parser("apply", help="执行方案")
    apply_parser.add_argument("--plan-id", required=True)
    apply_parser.add_argument("--target", required=True)
    apply_parser.add_argument("--confirm", action="store_true")
    apply_parser.add_argument("--mode", choices=["copy", "move"], default="copy")

    args = parser.parse_args()
    raise SystemExit(command_plan(args) if args.command == "plan" else command_apply(args))


if __name__ == "__main__":
    main()
