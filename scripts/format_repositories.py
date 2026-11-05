#!/usr/bin/env python3
"""Format local MOD repository source TOMLs.

Run ``python format_repositories.py`` to format source files, or add ``--check``
to verify formatting without writing. Requires Python 3.11+ (stdlib tomllib).
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "repositories.toml"
REPOSITORY_HEADER = re.compile(r"(?m)^\[\[repositories\]\][ \t]*(?:\r?\n|$)")
ASSIGNMENT = re.compile(r"^\s*([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)\s*=")
NOTE_ASSIGNMENT = re.compile(r"^\s*(note(?:_i18n\.[A-Za-z0-9_-]+)?)\s*=")
NAME_ORDER = ["name_i18n.zh-CN", "name_i18n.zh-TW", "name_i18n.en", "name_i18n.ko", "name_i18n.ja"]
GROUP_ORDER = ["group_i18n.zh-CN", "group_i18n.zh-TW", "group_i18n.en", "group_i18n.ko", "group_i18n.ja"]
BASE_ORDER = NAME_ORDER + GROUP_ORDER + ["provider", "username", "repository", "region"]
NOTE_LOCALE_ORDER = ["zh-CN", "zh-TW", "en", "ko", "ja"]


class FormatError(ValueError):
    """Raised when a source does not match the known repository layout."""


def parse_toml(text: str, label: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"{label}: invalid TOML: {error}") from error


def semantic_values(data: dict) -> dict:
    """Ignore only legacy keys intentionally removed by this formatter."""
    result = copy.deepcopy(data)
    for repository in result.get("repositories", []):
        for legacy_key in ("name", "group", "note"):
            repository.pop(legacy_key, None)
        repository.setdefault("region", "")
    return result


def assignment_key(line: str) -> str | None:
    match = ASSIGNMENT.match(line)
    return match.group(1) if match else None


def _find_unescaped(text: str, token: str, start: int) -> int:
    position = start
    while True:
        position = text.find(token, position)
        if position < 0:
            return -1
        if token == "'''":
            return position
        backslashes = 0
        cursor = position - 1
        while cursor >= 0 and text[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return position
        position += len(token)


def statement_end(lines: list[str], start: int) -> int:
    """Return the first line after a string-valued TOML assignment."""
    line = lines[start]
    rhs = line.split("=", 1)[1].lstrip()
    delimiter = next((quote for quote in ('"""', "'''" ) if rhs.startswith(quote)), None)
    if delimiter is None:
        return start + 1

    opener = line.find(delimiter, line.find("=") + 1)
    close = _find_unescaped(line, delimiter, opener + len(delimiter))
    if close >= 0:
        return start + 1
    for index in range(start + 1, len(lines)):
        if _find_unescaped(lines[index], delimiter, 0) >= 0:
            return index + 1
    raise FormatError(f"Unclosed multiline TOML string on line {start + 1}")


def _line_ending(line: str, fallback: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return fallback


def _section_index(lines: list[str], title: str, start: int = 0) -> int:
    matches = [index for index in range(start, len(lines)) if lines[index].strip() == title]
    if len(matches) != 1:
        raise FormatError(f"Expected one {title!r} section, found {len(matches)}")
    return matches[0]


def format_repository_block(header: str, body: str, label: str, fallback_newline: str) -> str:
    lines = body.splitlines(keepends=True)
    download_index = _section_index(lines, "# 下载方式")
    note_index = _section_index(lines, "# 仓库备注", download_index + 1)
    basic_index = _section_index(lines, "# 仓库基本信息", 0)
    if not basic_index < download_index < note_index:
        raise FormatError(f"{label}: repository sections are out of order")

    metadata = lines[:download_index]
    fields: dict[str, str] = {}
    field_indices: set[int] = set()
    for index, line in enumerate(metadata):
        key = assignment_key(line)
        if key is None:
            continue
        if key in fields:
            raise FormatError(f"{label}: duplicate basic field {key}")
        if "\n" in line.rstrip("\r\n"):
            raise FormatError(f"{label}: basic field {key} is not a single-line assignment")
        fields[key] = line
        field_indices.add(index)

    enabled = fields.pop("enabled", None)
    if enabled is None:
        raise FormatError(f"{label}: missing enabled field")
    enabled_match = re.match(r"^\s*enabled\s*=\s*(true|false)(\s+#.*)?(?:\r?\n)?$", enabled)
    if enabled_match is None:
        raise FormatError(f"{label}: enabled must be true or false")
    enabled_value, enabled_comment = enabled_match.groups()
    newline = _line_ending(header, fallback_newline)
    enabled_line = f"enabled = {enabled_value}{enabled_comment or ''}{newline}"

    # Legacy single-language fields were replaced by their i18n counterparts.
    for key in ("name", "group", "note"):
        fields.pop(key, None)

    if "region" not in fields:
        fields["region"] = f'region = ""{newline}'

    known_lines: list[str] = []
    for key in BASE_ORDER:
        if key in fields:
            known_lines.append(fields.pop(key))
    extra_assignments = [fields[key] for key in fields]
    other_metadata = [
        line
        for index, line in enumerate(metadata)
        if index not in field_indices and index != basic_index
    ]
    sorted_metadata = [enabled_line, lines[basic_index], *known_lines, *extra_assignments, *other_metadata]

    note_lines = lines[note_index + 1 :]
    note_spans: list[tuple[str, int, int]] = []
    index = 0
    while index < len(note_lines):
        match = NOTE_ASSIGNMENT.match(note_lines[index])
        if not match:
            index += 1
            continue
        key = match.group(1)
        end = statement_end(note_lines, index)
        note_spans.append((key, index, end))
        index = end

    localized_notes = [entry for entry in note_spans if entry[0].startswith("note_i18n.")]
    locales_present = [key.removeprefix("note_i18n.") for key, _, _ in localized_notes]
    if len(locales_present) != len(set(locales_present)):
        raise FormatError(f"{label}: duplicate note_i18n field")
    locale_priority = {locale: index for index, locale in enumerate(NOTE_LOCALE_ORDER)}
    localized_notes.sort(key=lambda entry: (locale_priority.get(entry[0].removeprefix("note_i18n."), len(locale_priority)), entry[0]))

    if note_spans:
        first = note_spans[0][1]
        last = note_spans[-1][2]
        statements = {key: note_lines[start:end] for key, start, end in note_spans}
        separators = [
            note_lines[note_spans[index][2] : note_spans[index + 1][1]]
            for index in range(len(note_spans) - 1)
        ]
        note_replacement: list[str] = []
        for index, entry in enumerate(localized_notes):
            note_replacement.extend(statements[entry[0]])
            if index < len(separators):
                note_replacement.extend(separators[index])
        for separator in separators[len(localized_notes) :]:
            note_replacement.extend(separator)
        note_replacement.extend(note_lines[last:])
        note_lines = note_lines[:first] + note_replacement

    return header + "".join(sorted_metadata + lines[download_index:note_index + 1] + note_lines)


def format_source_text(text: str, label: str) -> tuple[str, int]:
    before = parse_toml(text, label)
    matches = list(REPOSITORY_HEADER.finditer(text))
    repositories = before.get("repositories", [])
    if len(matches) != len(repositories):
        raise FormatError(f"{label}: found {len(matches)} repository headers for {len(repositories)} parsed entries")
    if not matches:
        raise FormatError(f"{label}: no [[repositories]] entries found")

    newline = "\r\n" if "\r\n" in text else "\n"
    output: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        output.append(text[cursor : match.start()])
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        output.append(format_repository_block(match.group(0), text[match.end() : end], label, newline))
        cursor = end
    output.append(text[cursor:])
    formatted = "".join(output)

    after = parse_toml(formatted, label)
    if semantic_values(before) != semantic_values(after):
        raise FormatError(f"{label}: formatting unexpectedly changed repository data")
    return formatted, len(repositories)


def source_files() -> list[Path]:
    if not INDEX.is_file():
        raise FormatError(f"Missing source index: {INDEX}")
    index = parse_toml(INDEX.read_text(encoding="utf-8-sig"), INDEX.name)
    paths: list[Path] = []
    for source in index.get("repository_sources", []):
        url = source.get("url")
        if not isinstance(url, str) or not url.lower().endswith(".toml") or "://" in url:
            continue
        path = (ROOT / url).resolve()
        if ROOT not in path.parents:
            raise FormatError(f"Repository source escapes the project directory: {url}")
        if not path.is_file():
            raise FormatError(f"Repository source does not exist: {url}")
        if path not in paths:
            paths.append(path)
    if not paths:
        raise FormatError("No local TOML repository sources found in repositories.toml")
    return paths


def _self_test() -> None:
    fixture = '''[[repositories]]
# 仓库基本信息
name_i18n.en = "Example"
enabled = false # keep enabled comment
name = "Legacy name"
group = "Legacy group"
name_i18n.ko = "예시"
name_i18n.zh-TW = "範例"
name_i18n.ja = "例"
name_i18n.zh-CN = "示例"
group_i18n.en = "Tools"
group_i18n.ko = "도구"
group_i18n.ja = "ツール"
group_i18n.zh-TW = "工具"
group_i18n.zh-CN = "工具"
provider = "github"
username = "owner"
repository = "repo"
# 下载方式
download_mode = "release"
# 仓库备注
note_i18n.en = """English note"""
note = "Legacy note"
note_i18n.zh-CN = """中文备注"""
note_i18n.ko = """한국어 메모"""
note_i18n.ja = """日本語メモ"""
note_i18n.zh-TW = """繁體備註"""
'''
    for newline in ("\\n", "\\r\\n"):
        source = fixture.replace("\\n", newline)
        formatted, count = format_source_text(source, "self-test.toml")
        parsed = parse_toml(formatted, "self-test.toml")["repositories"][0]
        assert count == 1
        assert formatted.splitlines()[1] == "enabled = false # keep enabled comment"
        assert all(key not in parsed for key in ("name", "group", "note"))
        assert parsed["region"] == ""
        assert list(parsed["name_i18n"]) == NOTE_LOCALE_ORDER
        assert list(parsed["group_i18n"]) == NOTE_LOCALE_ORDER
        assert list(parsed["note_i18n"]) == NOTE_LOCALE_ORDER
        if newline == "\\r\\n":
            assert "\\n" not in formatted.replace("\\r\\n", ""), "CRLF line endings were not preserved"
        again, _ = format_source_text(formatted, "self-test.toml")
        assert again == formatted, "formatter is not idempotent"


def main() -> int:
    parser = argparse.ArgumentParser(description="Format local MOD repository source TOMLs.")
    parser.add_argument("--check", action="store_true", help="report files needing formatting without writing")
    parser.add_argument("--self-test", action="store_true", help="run the built-in formatter behavior test")
    args = parser.parse_args()

    try:
        if args.self_test:
            _self_test()
            print("Formatter self-test passed.")
            return 0

        updates: list[tuple[Path, bytes, int]] = []
        for path in source_files():
            raw = path.read_bytes()
            bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
            text = raw[len(bom) :].decode("utf-8")
            formatted, count = format_source_text(text, path.name)
            new_raw = bom + formatted.encode("utf-8")
            if new_raw != raw:
                updates.append((path, new_raw, count))

        if args.check:
            if updates:
                for path, _, _ in updates:
                    print(f"Needs formatting: {path.relative_to(ROOT)}", file=sys.stderr)
                return 1
            print(f"All {len(source_files())} local repository source files are formatted.")
            return 0

        for path, content, _ in updates:
            path.write_bytes(content)
        if updates:
            for path, _, count in updates:
                print(f"Formatted {path.relative_to(ROOT)} ({count} repositories)")
        else:
            print(f"All {len(source_files())} local repository source files already match the format.")
        return 0
    except (OSError, UnicodeError, FormatError, AssertionError) as error:
        print(f"format_repositories.py: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
