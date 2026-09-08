---
name: Bug report
about: Something behaves incorrectly
title: ''
labels: bug
assignees: ''
---

<!--
NEVER attach a real HAR capture, evidence database, export or screenshot of a
real account. They contain personal data. Build a minimal synthetic reproducer
instead — the tests in tests/ show how.
-->

## What happened

<!-- Observed behaviour. Paste the exact error message if there is one. -->

## What you expected

## Reproduction

```sh
# The exact command or minimal script.
```

## Environment

- CrotDalam version: <!-- python -c "import crotdalam; print(crotdalam.__version__)" -->
- Python version: <!-- python --version -->
- OS:
- Installed with: <!-- pip install -e . | pip install . | running from a clone -->
- Optional extras: <!-- pdf / dev / none -->

## Checks

- [ ] I am on the latest version
- [ ] `python -m unittest discover -s tests` passes on my machine
- [ ] This report contains **no real captured data**
- [ ] I have read [`docs/TROUBLESHOOTING.md`](../../docs/TROUBLESHOOTING.md)

<!--
If a command exits saying the collection engine is not part of this release,
that is expected behaviour, not a bug. See docs/SCOPE.md.
-->
