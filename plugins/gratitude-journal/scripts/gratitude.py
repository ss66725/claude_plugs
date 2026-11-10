#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
幸福课 · 三件好事（Claude 插件版）

    python gratitude.py today  [--date 2026-11-10] [--json]
    python gratitude.py add    "今天把卡了很久的问题解决了" [--why "..."] [--slot 1] [--date ...]
    python gratitude.py review [--days 7] [--date ...] [--json]

数据放在 D:\\02ai_practice\\幸福课，一天一个 Markdown，按月分文件夹。可以用 --data-dir 或环境变量改动。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_DATA_DIR = r"D:\02ai_practice\幸福课"
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
SLOTS = 3
HEADING_ENTRIES = "## 三件好事"
HEADING_WHY = "## 为什么它们会发生（可选）"


# ---------------------------------------------------------------------------
# 日期与模板
# ---------------------------------------------------------------------------

def day_key(moment: date | None = None) -> str:
    moment = moment or date.today()
    return f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}"


def parse_key(value: str | None) -> str:
    if not value:
        return day_key()
    datetime.strptime(value, "%Y-%m-%d")  # 格式不对就抛错，让调用者知道
    return value


def weekday_of(key: str) -> str:
    return WEEKDAYS[datetime.strptime(key, "%Y-%m-%d").weekday()]


def day_file(data_dir: str, key: str) -> Path:
    return Path(data_dir) / key[:7] / f"{key}.md"


def render_template(key: str) -> str:
    return "\n".join([
        f"# {key} · {weekday_of(key)}",
        "",
        "> 幸福课 · 每天记三件让自己感到幸运或开心的事。",
        "",
        HEADING_ENTRIES,
        "",
        "1. ",
        "2. ",
        "3. ",
        "",
        HEADING_WHY,
        "",
        "",
        "## 今天的心情",
        "",
        "- [ ] 很好　- [ ] 不错　- [ ] 一般　- [ ] 低落",
        "",
        "---",
        "",
    ])


# ---------------------------------------------------------------------------
# 解析与写入
# ---------------------------------------------------------------------------

def section_range(lines: list[str], heading: str) -> tuple[int, int] | None:
    start = next((i for i, line in enumerate(lines) if line.strip() == heading), None)
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^##\s", lines[i]):
            end = i
            break
    return start, end


def read_entries(content: str) -> list[str]:
    lines = content.splitlines()
    span = section_range(lines, HEADING_ENTRIES)
    if span is None:
        return []
    start, end = span
    found = []
    for line in lines[start + 1:end]:
        matched = re.match(r"^\d+\.\s+(.+?)\s*$", line)
        if matched and matched.group(1).strip():
            found.append(matched.group(1).strip())
    return found


def fill_slot(content: str, text: str, slot: int | None) -> dict:
    lines = content.splitlines()
    span = section_range(lines, HEADING_ENTRIES)
    if span is None:
        raise ValueError(f"文件里没有「{HEADING_ENTRIES}」这一段，请先修好模板")
    start, end = span

    if slot is not None:
        if slot < 1:
            raise ValueError(f"第几号要写正整数，收到的是 {slot}")
        for i in range(start + 1, end):
            matched = re.match(r"^(\d+)\.\s*(.*)$", lines[i])
            if matched and int(matched.group(1)) == slot:
                if matched.group(2).strip():
                    raise ValueError(f"第 {slot} 条已经写了：{matched.group(2).strip()}")
                lines[i] = f"{slot}. {text}"
                return {"content": "\n".join(lines), "slot": slot}
        last = max((i for i in range(start + 1, end) if re.match(r"^\d+\.\s+\S", lines[i])), default=None)
        lines.insert((last if last is not None else start) + 1, f"{slot}. {text}")
        return {"content": "\n".join(lines), "slot": slot}

    for i in range(start + 1, end):
        matched = re.match(r"^(\d+)\.\s*(.*)$", lines[i])
        if matched and not matched.group(2).strip():
            lines[i] = f"{matched.group(1)}. {text}"
            return {"content": "\n".join(lines), "slot": int(matched.group(1))}

    existing = len(read_entries("\n".join(lines)))
    next_slot = existing + 1
    last = max((i for i in range(start + 1, end) if re.match(r"^\d+\.\s+\S", lines[i])), default=None)
    lines.insert((last if last is not None else start) + 1, f"{next_slot}. {text}")
    return {"content": "\n".join(lines), "slot": next_slot}


def fill_why(content: str, slot: int, why: str) -> str:
    lines = content.splitlines()
    span = section_range(lines, HEADING_WHY)
    if span is None:
        return content
    start, end = span
    insert_at = end
    while insert_at - 1 > start and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, f"- 第 {slot} 条：{why}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 读写
# ---------------------------------------------------------------------------

def ensure_day(data_dir: str, key: str) -> dict:
    path = day_file(data_dir, key)
    if path.exists():
        return {"file": str(path), "key": key, "created": False, "content": path.read_text(encoding="utf-8")}
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_template(key)
    path.write_text(content, encoding="utf-8")
    return {"file": str(path), "key": key, "created": True, "content": content}


def add_entry(data_dir: str, text: str, why: str | None, key: str, slot: int | None) -> dict:
    day = ensure_day(data_dir, key)
    filled = fill_slot(day["content"], text, slot)
    content = filled["content"]
    if why and why.strip():
        content = fill_why(content, filled["slot"], why.strip())
    Path(day["file"]).write_text(content, encoding="utf-8")
    return {"file": day["file"], "key": key, "slot": filled["slot"], "entries": read_entries(content)}


def review(data_dir: str, days: int, key: str) -> dict:
    total = min(max(days, 1), 120)
    anchor = datetime.strptime(key, "%Y-%m-%d").date()
    rows = []
    for offset in range(total - 1, -1, -1):
        current = day_key(anchor - timedelta(days=offset))
        path = day_file(data_dir, current)
        entries = read_entries(path.read_text(encoding="utf-8")) if path.exists() else []
        rows.append({
            "date": current,
            "weekday": weekday_of(current),
            "entries": len(entries),
            "done": len(entries) >= SLOTS,
            "text": entries,
        })

    streak = 0
    cursor = len(rows) - 1
    if cursor >= 0 and rows[cursor]["entries"] == 0:
        cursor -= 1
    while cursor >= 0 and rows[cursor]["entries"] > 0:
        streak += 1
        cursor -= 1

    return {
        "days": rows,
        "total": total,
        "streak": streak,
        "completed": sum(1 for row in rows if row["done"]),
        "recorded": sum(1 for row in rows if row["entries"] > 0),
        "missing": [row["date"] for row in rows if row["entries"] == 0],
    }


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def progress_line(entries: int) -> str:
    head = f"幸福课 · 三件好事：已记 {entries}/{SLOTS}"
    if entries >= SLOTS:
        return head + " ✓ 今天完成"
    if entries == 0:
        return head + "（还没开始）"
    return head


def human_today(day: dict) -> str:
    entries = read_entries(day["content"])
    lines = [
        f"{day['key']} · {weekday_of(day['key'])}",
        f"文件：{day['file']}" + ("（刚建好）" if day["created"] else ""),
        progress_line(len(entries)),
    ]
    for index, entry in enumerate(entries, start=1):
        lines.append(f"  {index}. {entry}")
    if len(entries) < SLOTS:
        lines.append(f"还差 {SLOTS - len(entries)} 条。")
    return "\n".join(lines)


def human_review(result: dict) -> str:
    lines = [
        f"最近 {result['total']} 天：记了 {result['recorded']} 天，其中 {result['completed']} 天写满三条",
        f"当前连续：{result['streak']} 天" + ("（今天还没写，从昨天算起）" if result["days"] and result["days"][-1]["entries"] == 0 else ""),
        "",
    ]
    for row in result["days"]:
        mark = "✓" if row["done"] else ("·" if row["entries"] else "空")
        lines.append(f"  {row['date']} {row['weekday']}  {mark}  {row['entries']} 条")
    if result["missing"]:
        lines.append("")
        lines.append("空着的日子：" + "、".join(result["missing"]))
    return "\n".join(lines)


def data_dir_of(args) -> str:
    return args.data_dir or os.environ.get("GRATITUDE_DATA_DIR") or DEFAULT_DATA_DIR


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="幸福课 · 每天记三件好事")
    parser.add_argument("--data-dir", help="记录目录，默认 D:\\02ai_practice\\幸福课")
    sub = parser.add_subparsers(dest="command", required=True)

    today_parser = sub.add_parser("today", help="显示今天的文件（不存在就建）")
    today_parser.add_argument("--date")
    today_parser.add_argument("--json", action="store_true")

    add_parser = sub.add_parser("add", help="记一条好事")
    add_parser.add_argument("text")
    add_parser.add_argument("--why")
    add_parser.add_argument("--slot", type=int)
    add_parser.add_argument("--date")
    add_parser.add_argument("--json", action="store_true")

    review_parser = sub.add_parser("review", help="最近 N 天的情况")
    review_parser.add_argument("--days", type=int, default=7)
    review_parser.add_argument("--date")
    review_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    directory = data_dir_of(args)
    key = parse_key(getattr(args, "date", None))

    if args.command == "today":
        day = ensure_day(directory, key)
        if args.json:
            print(json.dumps({
                "file": day["file"], "key": day["key"], "created": day["created"],
                "entries": read_entries(day["content"]), "content": day["content"],
            }, ensure_ascii=False, indent=2))
        else:
            print(human_today(day))
        return

    if args.command == "add":
        result = add_entry(directory, args.text.strip(), args.why, key, args.slot)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"已写入第 {result['slot']} 条：{args.text.strip()}")
            print(progress_line(len(result["entries"])))
            print(f"文件：{result['file']}")
        return

    result = review(directory, args.days, key)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(human_review(result))


if __name__ == "__main__":
    main()
