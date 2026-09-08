## What this changes

## Why

<!-- The problem being solved. Link the issue if there is one. -->

## Type

- [ ] Bug fix
- [ ] New capability
- [ ] Documentation
- [ ] Refactor / internal
- [ ] Breaking change

## How it was tested

```sh
python -m unittest discover -s tests
python -m pyflakes crotdalam/ tests/
python -m coverage run -m unittest discover -s tests && python -m coverage report --include="crotdalam/*"
```

<!-- Paste the results. -->

## Checklist

- [ ] All tests pass
- [ ] `pyflakes` is clean
- [ ] Coverage did not regress
- [ ] New code has tests, including the boundary cases that must fail
- [ ] Modules I added carry a docstring stating what they do **and refuse to do**
- [ ] Bounds on untrusted input are documented and tested
- [ ] Documentation in `docs/` is updated
- [ ] `CHANGELOG.md` has an entry for user-visible changes
- [ ] **No real captured data** in the diff, tests or fixtures
- [ ] No new runtime dependency, or it is justified below

## Scope

- [ ] This does not add CAPTCHA solving, signature generation, fingerprint
      spoofing, evasion proxying or decoy traffic (see `docs/SCOPE.md`)

## Behaviour changes downstream users would notice

<!-- Or "none". -->
