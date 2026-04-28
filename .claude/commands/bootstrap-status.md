---
description: Print a one-shot health check of the Phase 0 scaffolding.
---

# /bootstrap-status

Prints, in order:

1. Whether `CLAUDE.md` is present at the repo root.
2. The number of files in `.claude/commands/`, `.claude/agents/`, and
   `.claude/skills/` (asset library size).
3. The latest commit (short hash + subject).
4. The latest annotated tag.
5. Whether `evals/runs/` contains any run yet.

Run the following bash blocks and report the outputs verbatim, then add
a one-line verdict (`OK` if CLAUDE.md is present and at least one asset
exists in each of commands/agents/skills, otherwise `INCOMPLETE` with
the missing pieces named).

```bash
test -f CLAUDE.md && echo "CLAUDE.md: present" || echo "CLAUDE.md: MISSING"
```

```bash
for d in .claude/commands .claude/agents .claude/skills; do
  if [ -d "$d" ]; then
    n=$(find "$d" -type f ! -name '.gitkeep' | wc -l | tr -d ' ')
    echo "$d: $n file(s)"
  else
    echo "$d: MISSING"
  fi
done
```

```bash
git log -1 --pretty=format:'%h %s' 2>/dev/null || echo "no commits yet"
```

```bash
git describe --tags --abbrev=0 2>/dev/null || echo "no tags yet"
```

```bash
if [ -d evals/runs ]; then
  n=$(find evals/runs -type f -name '*.json' | wc -l | tr -d ' ')
  echo "evals/runs/: $n run(s)"
else
  echo "evals/runs/: MISSING"
fi
```
