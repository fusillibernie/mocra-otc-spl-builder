#!/usr/bin/env python3
"""PreToolUse gate that makes the verification agents mandatory.

  edit   Edit/Write/NotebookEdit needs a repo-mapper run earlier in this session.
  commit `git commit` / `git push` needs an independent-reviewer run after the
         most recent edit.

It reads the session transcript, so a run counts only if it really happened.
Fails open (allows) when the transcript cannot be read, so a broken hook never
locks the session. Blocks with exit code 2 and a message Claude sees.
"""
import json
import sys

AGENT_TOOLS = {"Agent", "Task"}
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
# Edits that need no mapping: agent/hook config, scratch space.
EXEMPT = ("/.claude/", "/tmp/", "/scratchpad/")


def tool_uses(path):
    """Yield (name, input) for every tool call in the main session, in order."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("isSidechain"):
                continue
            content = (event.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    yield item.get("name", ""), item.get("input") or {}


def ran(calls, agent):
    return [i for i, (n, a) in enumerate(calls)
            if n in AGENT_TOOLS and a.get("subagent_type") == agent]


def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    path = payload.get("transcript_path")

    if tool in EDIT_TOOLS:
        target = inp.get("file_path") or inp.get("notebook_path") or ""
        if any(part in target for part in EXEMPT):
            return 0
        need, agent = "edit", "repo-mapper"
    elif tool == "Bash":
        words = (inp.get("command") or "").split()
        if not any(words[i:i + 2] in (["git", "commit"], ["git", "push"])
                   for i in range(len(words))):
            return 0
        need, agent = "commit", "independent-reviewer"
    else:
        return 0

    try:
        calls = list(tool_uses(path))
    except (OSError, TypeError):
        return 0

    runs = ran(calls, agent)
    if need == "edit":
        if runs:
            return 0
        print("Blocked: run the repo-mapper agent first "
              "('where does the code handle X?') before editing in this repo.",
              file=sys.stderr)
        return 2

    edits = [i for i, (n, a) in enumerate(calls) if n in EDIT_TOOLS
             and not any(p in (a.get("file_path") or a.get("notebook_path") or "")
                         for p in EXEMPT)]
    if not edits or (runs and runs[-1] > edits[-1]):
        return 0
    print("Blocked: run the independent-reviewer agent on the finished diff "
          "(goal + diff) after your last edit, then fix or report its "
          "findings, before committing or pushing.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
