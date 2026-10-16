#!/usr/bin/env python3
"""Check the Git index for private material without printing matched values.

Use --include-untracked before the first commit. This audit is a guardrail, not a
secret-scanner substitute; inspect the complete diff before publishing.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import sys

PRIVATE_PARTS = frozenset({
    "private", "backups", "logs", "downloads", "vendor", "state", "controller-data",
    "escrow", "support-bundles", "recordings", "models", "saved_model", ".terraform",
    ".venv", "__pycache__", "node_modules",
})
PRIVATE_SUFFIXES = (".img", ".img.gz", ".bin", ".zip", ".tar", ".tar.gz", ".tgz", ".7z",
                    ".onnx", ".onnx.data", ".tflite", ".npy", ".npz", ".h5", ".keras",
                    ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".mp4", ".pcm", ".raw",
                    ".s16le", ".pem", ".key", ".p12", ".pfx", ".psk", ".log",
                    ".db", ".sqlite", ".sqlite3", ".tfstate", ".tfplan", ".tfvars", ".pyc")
PRIVATE_NAMES = frozenset({"secrets.yaml", "secrets.yml", "credentials.json", "credentials.tfrc.json"})
MAX_TEXT_BYTES = 2 * 1024 * 1024
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
MAC = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])")
DOC_NETWORKS = tuple(ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"))
SECRETS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub credential", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("JWT credential", re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b")),
    ("cloud access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
)
ASSIGNMENT = re.compile(
    r'''(?ix)["']?\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|psk|secret|token)["']?\s*[:=]\s*["']([^"'\r\n]{4,})["']'''
)
PLAIN_ASSIGNMENT = re.compile(
    r"(?i)^\s*(?:-\s*)?(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|psk|secret|token)\s*[:=]\s*([^\s\"'#]{4,})\s*(?:#.*)?$"
)
# Exact translated form labels, not credential values. Keep this list narrow.
SAFE_UI_LABELS = frozenset({"Service token", "Токен сервиса", "Dienst-Token",
                            "Token del servicio", "Jeton du service"})


def path_problem(name: str) -> str | None:
    path = Path(name)
    lower = name.lower()
    if any(part.lower() in PRIVATE_PARTS for part in path.parts):
        return "private directory"
    if (path.name.lower() in PRIVATE_NAMES or lower.endswith(PRIVATE_SUFFIXES)
            or ".local." in lower or ".tfstate." in lower):
        return "private file or generated artifact"
    if path.name.startswith(".env") and path.name != ".env.example":
        return "environment credentials"
    if path.parts and path.parts[0] == "inventory" and path.name != "devices.example.json":
        return "live inventory"
    return None


def content_problems(data: bytes) -> list[tuple[int, str]]:
    if len(data) > MAX_TEXT_BYTES:
        return [(0, "oversized public source file")]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [(0, "binary content")]
    if "\x00" in text:
        return [(0, "binary content")]
    problems = set()
    for line_no, line in enumerate(text.splitlines(), 1):
        for label, pattern in SECRETS:
            if pattern.search(line):
                problems.add((line_no, label))
        for match in IPV4.finditer(line):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            if not (address.is_loopback or address.is_unspecified
                    or any(address in network for network in DOC_NETWORKS)):
                problems.add((line_no, "live IPv4 address"))
        if MAC.search(line):
            problems.add((line_no, "device MAC address"))
        matches = [*ASSIGNMENT.finditer(line), *PLAIN_ASSIGNMENT.finditer(line)]
        for match in matches:
            value = match.group(1)
            if not (value.startswith(("${", "<", "REPLACE_", "EXAMPLE_"))
                    or value.lower().startswith(("example", "dummy", "test", "placeholder"))
                    or value.lower() in {"none", "null", "false", "true", "redacted"}
                    or value in SAFE_UI_LABELS):
                problems.add((line_no, "possible credential assignment"))
    return sorted(problems)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)


def audit(root: Path, include_untracked: bool = False) -> tuple[int, list[str]]:
    issues = []
    entries = git(root, "ls-files", "--stage", "-z").split(b"\0")
    checked = set()
    for entry in entries:
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        name = os.fsdecode(raw_name)
        mode, oid, stage = metadata.split()
        checked.add(name)
        reason = path_problem(name)
        if reason:
            issues.append(f"{name}: {reason}")
            continue
        if mode not in (b"100644", b"100755") or stage != b"0":
            issues.append(f"{name}: non-regular or unmerged index entry")
            continue
        size = int(git(root, "cat-file", "-s", oid.decode()))
        if size > MAX_TEXT_BYTES:
            issues.append(f"{name}: oversized public source file")
            continue
        data = git(root, "cat-file", "blob", oid.decode())
        for line, label in content_problems(data):
            issues.append(f"{name}:{line}: {label}")
        # Check unstaged edits too; checking the index still catches a staged
        # credential even if it has already been removed from the working file.
        file = root / name
        if file.is_symlink():
            issues.append(f"{name}: working file is a symlink")
        elif file.is_file() and file.stat().st_size <= MAX_TEXT_BYTES:
            for line, label in content_problems(file.read_bytes()):
                issues.append(f"{name}:{line}: {label}")
    if include_untracked:
        for raw_name in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
            if not raw_name:
                continue
            name = os.fsdecode(raw_name)
            checked.add(name)
            reason = path_problem(name)
            file = root / name
            if reason or file.is_symlink():
                issues.append(f"{name}: {reason or 'symlink'}")
            elif file.stat().st_size > MAX_TEXT_BYTES:
                issues.append(f"{name}: oversized public source file")
            else:
                for line, label in content_problems(file.read_bytes()):
                    issues.append(f"{name}:{line}: {label}")
    return len(checked), sorted(set(issues))


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--include-untracked", action="store_true")
    args = cli.parse_args(argv)
    try:
        count, issues = audit(args.root, args.include_untracked)
    except (OSError, subprocess.CalledProcessError, ValueError):
        print("Public audit could not read the Git index or working files.", file=sys.stderr)
        return 1
    if not count:
        print("No indexed files; stage public source or use --include-untracked.", file=sys.stderr)
        return 1
    if issues:
        print("Public audit failed (matched values are intentionally omitted):", file=sys.stderr)
        for issue in issues:
            print(f"  {issue}", file=sys.stderr)
        return 1
    print(f"Public audit passed: {count} source files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
