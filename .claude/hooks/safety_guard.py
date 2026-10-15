#!/usr/bin/env python3
"""PreToolUse (Bash): block commands that delete broadly, rewrite history, or
touch production. Exit 2 with the reason so Claude asks the user instead.
rm -r is allowed only inside /tmp or a scratchpad directory."""
import json
import re
import sys

RULES = [
    (r"--prod(uction)?\b|test\s*=\s*False", "targets production (ESG production needs a named person's Approval)"),
    (r"\b(drop\s+(table|database|schema)|truncate\s+table|delete\s+from)\b", "destructive SQL"),
    (r"\bgit\s+push\b[^;&|]*(--force\b|--force-with-lease\b|\s-f\b)", "force push"),
    (r"\bgit\s+push\b[^;&|]*\s(origin\s+)?(main|master)\b", "push to the default branch"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard discards work"),
    (r"\bgit\s+clean\s+-\S*f", "git clean deletes untracked files"),
    (r"\bgit\s+branch\s+-D\b", "force-deleting a branch"),
    (r"\bfind\b[^;&|]*\s-delete\b|\bshred\b|\bmkfs\b|\bdd\s+[^;&|]*of=/dev/", "bulk or device-level delete"),
]
SAFE_ROOTS = ("/tmp/", "/var/tmp/")


def rm_problem(cmd):
    for m in re.finditer(r"\brm\s+([^;&|]*)", cmd):
        args = m.group(1).split()
        flags = [a for a in args if a.startswith("-")]
        if not any(re.search(r"r|R", f) or f == "--recursive" for f in flags if not f.startswith("--") or f == "--recursive"):
            continue
        targets = [a for a in args if not a.startswith("-")]
        if not targets or not all(
                t.startswith(SAFE_ROOTS) or "/scratchpad/" in t for t in targets) \
                or any(".." in t for t in targets):
            return "recursive rm outside /tmp or a scratchpad"
    return None


def main():
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
    reason = rm_problem(cmd)
    if not reason:
        for pattern, why in RULES:
            if re.search(pattern, cmd, re.I):
                reason = why
                break
    if reason:
        print(f"Blocked by hook: {reason}. Confirm this command with the user first.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
