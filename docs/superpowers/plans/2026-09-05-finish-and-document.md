# Finish and Document Plan

**Date**: 2026-09-05
**Status**: Done (design questions answered in the preceding brainstorming session)
**Spec**: `docs/superpowers/specs/2026-09-04-modernization-design.md`

**Goal:** Close the verified gaps left after the modernization, then rebuild the README and documentation around a reproducible demo with real screenshots.

**Decisions:**

1. Scope: finish and document. Fix the verified CI, packaging, typing and read-only gaps first, then the docs.
2. Django floor stays at 4.2. Add explicit minimum-version and current-version test jobs.
3. Documentation layout A: screenshot first, then capabilities, setup and a guided tour.
4. PyPy runs the test suite without coverage. CPython keeps the 100% line and branch gate.

---

### Task 1: Consolidate pytest configuration

- [x] Delete `pytest.ini`, move `pythonpath = ['.']` into `[tool.pytest.ini_options]`.
- [x] `uv run pytest` still collects 55 tests at 100% coverage.

### Task 2: Explicit strict Pyrefly

- [x] Set `preset = 'strict'` in `[tool.pyrefly]`.
- [x] Type check `test_redis_admin` alongside the package and tests.
- [x] Decorate the 12 overriding members with `@override` from `typing_extensions`.
- [x] Add `typing-extensions` as a runtime dependency.
- [x] `pyrefly check`, `mypy` and `basedpyright` all report zero errors.

### Task 3: Enforce the read-only admin

- [x] Tests: add, change and delete endpoints return 403, `delete_selected` is absent from the actions, a change page renders without a save button.
- [x] Implement `has_add_permission`, `has_change_permission` and `has_delete_permission` returning `False` on `RedisAdmin`.

### Task 4: Repair source-package testing

- [x] Include `test_redis_admin/**/*.py` in the sdist.
- [x] Stop tracking `test_redis_admin/db.sqlite3` and ignore `*.sqlite3`.
- [x] Extract the sdist and run its test suite.

### Task 5: PyPy without coverage

- [x] `tox.ini`: PyPy envs run `pytest --no-cov`.
- [x] `ci.yml`: upload coverage artifacts from CPython cells only.

### Task 6: Explicit Django compatibility jobs

- [x] `tox.ini`: `py312-django42`, `py313-django52`, `py314-django60`, and `py314-django61` envs pinned to their Django series.
- [x] `ci.yml`: a `django-compat` job running those envs.

### Task 7: Reproducible demo

- [x] `RedisAdminConfig` names the app **Redis** and `RedisValue.__str__` returns the key, so pages and breadcrumbs read naturally.
- [x] `test_redis_admin/settings_demo.py` layering demo-only settings over the test settings.
- [x] `test_redis_admin/demo.py`: migrate, create `admin`/`admin`, seed Redis with sample keys of every type, run the server.
- [x] Tests for the seeding and superuser helpers.

### Task 8: Screenshots

- [x] Capture the admin index, the changelist with search, and a detail page from the running demo into `docs/_static/`.

### Task 9: README and documentation

- [x] README: badges, hero screenshot, features, quick start, tour, configuration summary, demo, development, roadmap.
- [x] Docs: landing page, quick start, configuration reference, tour, demo, development, API reference.
- [x] Absolute image URLs in the README.

### Task 10: Verification

- [x] `tox -m check`, `tox -e coverage`, `tox -e docs`, `uv build`, sdist test run, PyPy env, Django compat envs.
