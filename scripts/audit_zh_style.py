#!/usr/bin/env python3
"""Report candidate template-like patterns in Chinese prose.

This is an editorial aid, not an AI detector. It never rewrites the input and
does not assign a human/AI score. Every hit requires contextual review.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


PATTERN_GROUPS: dict[str, list[tuple[str, str]]] = {
    "空泛引导": [
        ("worth_noting", r"值得注意的是|需要注意的是|需要强调的是"),
        ("self_evident", r"不可否认的是|毋庸置疑|众所周知"),
        ("era_opener", r"在当今[^，。；\n]{0,24}(?:时代|背景)(?:下|中)?"),
    ],
    "机械路标": [
        ("ordered_joiners", r"首先|其次|再次|最后"),
        ("summary_joiners", r"综上所述|总而言之|由此可见"),
        ("binary_joiners", r"一方面|另一方面"),
    ],
    "模板化抽象词": [
        ("enable", r"赋能|助力|注入新动能"),
        ("broad_analysis", r"深入探讨|多维度|全方位"),
        ("campaign_language", r"协同推进|构建闭环|持续发力|不断提升"),
        ("importance", r"不可忽视|至关重要|发挥关键作用"),
    ],
    "模糊权威": [
        ("vague_research", r"(?:大量|相关|已有)?研究表明"),
        ("vague_experts", r"专家认为|业内人士指出|有学者指出"),
        ("vague_data", r"相关数据显示|普遍认为"),
    ],
    "强行升华": [
        ("future_uplift", r"共同迈向(?:更加)?美好未来|美好未来|未来可期"),
        ("new_chapter", r"开启新篇章|迈上新台阶|开创新局面"),
        ("contribution", r"贡献力量|作出更大贡献"),
    ],
    "对话残留": [
        ("chat_open", r"(?:^|[。！？\n])\s*当然(?:可以)?[！!。]?"),
        ("helpful_close", r"希望(?:以上|这些)?(?:内容|信息)?(?:能|可以)?对您有所帮助"),
        ("offer_more", r"如果(?:您|你)(?:还)?需要[^。！？\n]{0,30}(?:告诉我|我可以)"),
        ("generated_wrapper", r"以下是(?:为您|根据您的要求)[^。！？\n]{0,30}"),
        ("ai_identity", r"作为(?:一个)?(?:AI|人工智能|语言模型)"),
    ],
    "重复因果骨架": [
        (
            "through_chain",
            r"通过[^。！？；\n]{0,45}(?:实现|提升|促进)[^。！？；\n]{0,45}(?:从而|进而|进一步)",
        ),
        (
            "not_but",
            r"不(?:仅|只是|单单|仅仅)?[^。！？；\n]{1,45}(?:而且|更是|而是)",
        ),
    ],
}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])")
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
MARKDOWN_PREFIX_RE = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)、]\s*)")
LEADING_PUNCT_RE = re.compile(r"^[\s\"'“”‘’《》〈〉（）()【】\[\]：:，,。！？!?；;—-]+")


def read_text(path: str, forced_encoding: str | None) -> tuple[str, str]:
    raw = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
    if forced_encoding:
        encodings = [forced_encoding]
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:80]:
        encodings = ["utf-16", "utf-8-sig", "utf-8", "gb18030"]
    else:
        encodings = ["utf-8-sig", "utf-8", "gb18030"]
    for encoding in encodings:
        if encoding is None:
            continue
        try:
            source_encoding = f"stdin/{encoding}" if path == "-" else encoding
            return raw.decode(encoding), source_encoding
        except UnicodeDecodeError:
            pass
    raise UnicodeError("无法按 UTF-8 或 GB18030 解码；可用 --encoding 指定编码。")


def mask_fenced_code(text: str) -> str:
    """Blank fenced code lines while preserving line numbers."""
    output: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        marker_match = re.match(r"(`{3,}|~{3,})", stripped)
        if marker_match:
            marker = marker_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
            elif marker[0] == fence_marker:
                in_fence = False
                fence_marker = ""
            output.append("\n" if line.endswith(("\n", "\r")) else "")
            continue
        output.append(("\n" if line.endswith(("\n", "\r")) else "") if in_fence else line)
    return "".join(output)


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def snippet(text: str, start: int, end: int, radius: int = 32) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    value = re.sub(r"\s+", " ", text[left:right]).strip()
    if left > 0:
        value = "…" + value
    if right < len(text):
        value += "…"
    return value


def sentence_records(text: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    offset = 0
    for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
        clean_line = MARKDOWN_PREFIX_RE.sub("", line.strip())
        local_offset = 0
        for part in SENTENCE_SPLIT_RE.split(clean_line):
            sent = part.strip()
            if not sent:
                local_offset += len(part)
                continue
            normalized = re.sub(r"\s+", "", sent)
            han_len = len(HAN_RE.findall(normalized))
            if han_len >= 4:
                records.append(
                    {
                        "line": line_no,
                        "text": sent,
                        "normalized": re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE),
                        "han_length": han_len,
                        "offset": offset + local_offset,
                    }
                )
            local_offset += len(part)
        offset += len(line)
    return records


def find_phrase_candidates(text: str) -> tuple[list[dict[str, object]], dict[str, int]]:
    candidates: list[dict[str, object]] = []
    group_counts: dict[str, int] = defaultdict(int)
    for group, patterns in PATTERN_GROUPS.items():
        for pattern_id, expression in patterns:
            for match in re.finditer(expression, text, flags=re.MULTILINE):
                group_counts[group] += 1
                candidates.append(
                    {
                        "kind": "phrase",
                        "group": group,
                        "pattern": pattern_id,
                        "line": line_number(text, match.start()),
                        "match": match.group(0).strip(),
                        "context": snippet(text, match.start(), match.end()),
                    }
                )
    return candidates, dict(group_counts)


def repeated_openings(sentences: list[dict[str, object]], prefix_len: int = 3) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    i = 0
    while i < len(sentences):
        text = LEADING_PUNCT_RE.sub("", str(sentences[i]["text"]))
        prefix = "".join(HAN_RE.findall(text))[:prefix_len]
        if len(prefix) < prefix_len:
            i += 1
            continue
        j = i + 1
        while j < len(sentences):
            other = LEADING_PUNCT_RE.sub("", str(sentences[j]["text"]))
            other_prefix = "".join(HAN_RE.findall(other))[:prefix_len]
            if other_prefix != prefix:
                break
            j += 1
        if j - i >= 3:
            candidates.append(
                {
                    "kind": "repeated_opening",
                    "line": sentences[i]["line"],
                    "count": j - i,
                    "prefix": prefix,
                    "context": " / ".join(str(item["text"])[:28] for item in sentences[i:j]),
                }
            )
        i = max(j, i + 1)
    return candidates


def similar_length_runs(sentences: list[dict[str, object]]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    qualifying: set[int] = set()
    for i in range(len(sentences) - 2):
        lengths = [int(sentences[k]["han_length"]) for k in range(i, i + 3)]
        mean = statistics.fmean(lengths)
        if min(lengths) >= 8 and max(lengths) - min(lengths) <= max(3, mean * 0.15):
            qualifying.update(range(i, i + 3))
    if not qualifying:
        return candidates

    indexes = sorted(qualifying)
    start = previous = indexes[0]
    for index in indexes[1:] + [indexes[-1] + 2]:
        if index == previous + 1:
            previous = index
            continue
        run = sentences[start : previous + 1]
        candidates.append(
            {
                "kind": "similar_sentence_lengths",
                "line": run[0]["line"],
                "count": len(run),
                "lengths": [item["han_length"] for item in run],
                "context": " / ".join(str(item["text"])[:24] for item in run),
            }
        )
        start = previous = index
    return candidates


def duplicate_sentences(sentences: list[dict[str, object]]) -> list[dict[str, object]]:
    by_text: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in sentences:
        normalized = str(item["normalized"])
        if len(normalized) >= 6:
            by_text[normalized].append(item)
    candidates: list[dict[str, object]] = []
    for items in by_text.values():
        if len(items) > 1:
            candidates.append(
                {
                    "kind": "duplicate_sentence",
                    "line": items[0]["line"],
                    "lines": [item["line"] for item in items],
                    "count": len(items),
                    "context": str(items[0]["text"]),
                }
            )
    return candidates


def paragraph_metrics(text: str) -> dict[str, object]:
    paragraphs = [re.sub(r"\s+", "", p) for p in re.split(r"\n\s*\n", text) if p.strip()]
    lengths = [len(HAN_RE.findall(p)) for p in paragraphs]
    lengths = [length for length in lengths if length > 0]
    if not lengths:
        return {"count": 0, "han_lengths": {"min": 0, "median": 0, "max": 0}}
    return {
        "count": len(lengths),
        "han_lengths": {
            "min": min(lengths),
            "median": round(statistics.median(lengths), 1),
            "max": max(lengths),
        },
    }


def analyze(text: str, source: str, encoding: str) -> dict[str, object]:
    masked = mask_fenced_code(text)
    sentences = sentence_records(masked)
    phrase_candidates, group_counts = find_phrase_candidates(masked)
    structural_candidates = (
        repeated_openings(sentences)
        + similar_length_runs(sentences)
        + duplicate_sentences(sentences)
    )
    han_count = len(HAN_RE.findall(masked))
    phrase_count = sum(group_counts.values())
    return {
        "disclaimer": "编辑候选审查，不是 AI 来源检测；命中项必须结合文体、引用和上下文人工判断。",
        "source": source,
        "encoding": encoding,
        "metrics": {
            "han_characters": han_count,
            "sentences": len(sentences),
            "paragraphs": paragraph_metrics(masked),
            "phrase_candidates": phrase_count,
            "phrase_candidates_per_1000_han": round(phrase_count * 1000 / han_count, 2)
            if han_count
            else 0,
            "phrase_groups": group_counts,
        },
        "candidates": sorted(
            phrase_candidates + structural_candidates,
            key=lambda item: (int(item.get("line", 0)), str(item.get("kind", ""))),
        ),
    }


def format_candidate(item: dict[str, object]) -> str:
    kind = item.get("kind")
    line = item.get("line", "?")
    if kind == "phrase":
        return f"L{line} [{item['group']}] {item['match']} | {item['context']}"
    if kind == "repeated_opening":
        return f"L{line} [重复开头] 连续 {item['count']} 句以“{item['prefix']}”开头 | {item['context']}"
    if kind == "similar_sentence_lengths":
        return f"L{line} [句长过齐候选] {item['count']} 句长度 {item['lengths']} | {item['context']}"
    if kind == "duplicate_sentence":
        return f"L{line} [重复句] 出现在行 {item['lines']} | {item['context']}"
    return f"L{line} [{kind}] {item.get('context', '')}"


def print_report(report: dict[str, object], limit: int) -> None:
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    paragraphs = metrics["paragraphs"]
    assert isinstance(paragraphs, dict)
    print(report["disclaimer"])
    print(f"来源：{report['source']}（编码：{report['encoding']}）")
    print(
        "概况："
        f"{metrics['han_characters']} 个汉字，{metrics['sentences']} 句，"
        f"{paragraphs['count']} 段；短语候选 {metrics['phrase_candidates']} 处。"
    )
    candidates = report["candidates"]
    assert isinstance(candidates, list)
    if not candidates:
        print("未发现预设候选。仍需人工检查论证、事实和语域。")
        return
    print("候选：")
    for item in candidates[:limit]:
        print("- " + format_candidate(item))
    if len(candidates) > limit:
        print(f"- 另有 {len(candidates) - limit} 项未显示；用 --json 查看全部。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="报告中文文本中的模板化候选；不判断 AI 来源，不修改文件。"
    )
    parser.add_argument("path", help="UTF-8/GB18030 文本或 Markdown 文件；用 - 读取 stdin")
    parser.add_argument("--encoding", help="强制输入编码，例如 utf-8 或 gb18030")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--limit", type=int, default=50, help="普通输出最多显示的候选数")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        text, encoding = read_text(args.path, args.encoding)
    except (OSError, UnicodeError) as error:
        print(f"读取失败：{error}", file=sys.stderr)
        return 2
    report = analyze(text, args.path, encoding)
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_report(report, max(1, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
