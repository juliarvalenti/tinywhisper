# Merge PR

Await CI checks, then merge when all pass.

## Steps

1. Watch checks until they complete:
```bash
gh pr checks <number> --watch
```
If `--watch` errors immediately (no checks reported yet), poll manually:
```bash
sleep 15 && gh pr checks <number>
```

2. If any check **fails**, fix the issue, commit, push, and re-run checks.

3. When all checks **pass**, merge with squash and delete the branch:
```bash
gh pr merge <number> --squash --delete-branch
```

4. Pull main to sync local:
```bash
git checkout main && git pull
```
