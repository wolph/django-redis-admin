# Modernization Design: django-redis-admin

**Date**: 2026-09-04  
**Status**: Approved  
**Target Repository**: `WoLpH/django-redis-admin`  
**Reference Standard**: `WoLpH/python-utils` (`~/workspace/python-utils`)

---

## 1. Overview and Goals

Modernize `django-redis-admin` to match the development standards, tooling, and infrastructure of `python-utils`.

### Key Objectives
1. Modern build system using `uv_build` backend and `pyproject.toml` configuration.
2. Code formatting and linting managed through `ruff.toml` and `codespell`.
3. Triple strict static type checking via `mypy` (with `django-stubs`), `basedpyright`, and `pyrefly`, with PEP 561 `py.typed` packaging.
4. Comprehensive automated test suite run across a multi-Python matrix (Python 3.10 through 3.14 and PyPy) using `tox-uv`, with a 100% line and branch coverage gate (`fail_under = 100`).
5. Modernized documentation using Markdown (`README.md`, `docs/`), `MyST-Parser`, and the `Furo` theme with `.readthedocs.yaml`.
6. Complete CI/CD workflows on GitHub Actions matching `python-utils` (`ci.yml`, `publish.yml`).

---

## 2. Packaging and Build System

### 2.1 Build Backend
- Migrate from legacy `setup.py` / `distutils` to `uv_build` backend:
  ```toml
  [build-system]
  requires = ['uv_build>=0.11,<0.13']
  build-backend = 'uv_build'

  [tool.uv.build-backend]
  module-root = ''
  module-name = 'redis_admin'
  source-include = ['tests/**/*.py', 'tox.ini']
  ```
- Retain a thin, backward-compatible `setup.py` shim for legacy pip/distutils workflows that read metadata from `pyproject.toml` or `__about__.py`.
- Ship a PEP 561 `redis_admin/py.typed` marker so consumers can inspect type annotations.

### 2.2 Project Metadata (`[project]`)
- Package name: `django-redis-admin`
- Target Python: `>=3.10`
- Target Django: `>=4.2`
- Static version: `"0.3.0"` in `pyproject.toml` and `redis_admin/__about__.py`
- Dependencies:
  - `redis>=4.0.0`
  - `django>=4.2`
- Classifiers: Python 3.10, 3.11, 3.12, 3.13, 3.14, CPython, PyPy, Typing :: Typed, Framework :: Django

### 2.3 Dependency Groups
- `docs`: `sphinx`, `furo`, `myst-parser`
- `test`: `pytest`, `pytest-cov`, `pytest-django`, `redis`, `fakeredis`
- `dev`: `ruff`, `mypy`, `basedpyright`, `pyrefly`, `codespell`, `django-stubs`, `types-redis`, `lefthook`, includes `test` and `docs`
- `tox`: `tox>=4`, `tox-uv>=1`, `tox-gh-actions`

---

## 3. Linting, Formatting, and Code Quality

### 3.1 Ruff Configuration (`ruff.toml`)
- Match `python-utils/ruff.toml` rules:
  - Target Python version: `py310`
  - Line length: 79 characters
  - Single quotes for docstrings and code literals (`flake8-quotes`)
  - Google docstring convention (`pydocstyle`)
  - Rules enabled: `A`, `ASYNC`, `B`, `C4`, `C90`, `COM`, `D`, `E`, `F`, `FA`, `I`, `ICN`, `INP`, `ISC`, `N`, `PERF`, `PIE`, `Q`, `RET`, `RUF`, `SIM`, `T20`, `TD`, `TRY`, `UP`
- Resolve all existing lint issues across `redis_admin/`, `test_redis_admin/`, and `tests/`.

### 3.2 Codespell
- Configure `[tool.codespell]` in `pyproject.toml` to check documentation and source code, ignoring cache directories and binary artifacts.

### 3.3 Git Hooks (`lefthook.yml`)
- Add `lefthook.yml` configuring pre-commit hooks for `ruff check --fix`, `ruff format`, `codespell`, and type checks.

---

## 4. Strict Type Checking

### 4.1 Type Checkers
Configure three distinct checkers in `pyproject.toml`:
1. `[tool.mypy]`:
   - `python_version = '3.10'`
   - `strict = true`
   - `check_untyped_defs = true`
   - Plugins: `mypy_django_plugin.main` with `django_settings_module = "test_redis_admin.settings"`
2. `[tool.pyright]`:
   - `typeCheckingMode = 'strict'`
   - `pythonVersion = '3.10'`
   - `reportMissingTypeStubs = false`
3. `[tool.pyrefly]`:
   - `python-version = '3.10'`
   - Checks `redis_admin` and `tests`

### 4.2 Source Typing Refactorings
- Fix dynamic `server_models` generation in `redis_admin/models.py` to satisfy type checkers.
- Provide explicit type annotations on model fields, class attributes, functions, and module variables.
- Clean up `RedisMeta` attribute dynamic lookups and `client.py` connection options.

---

## 5. Testing, Tox Matrix, and 100% Coverage

### 5.1 Pytest Configuration
- Move pytest options into `[tool.pytest.ini_options]` in `pyproject.toml` (or retain synced `pytest.ini`):
  - `DJANGO_SETTINGS_MODULE = "test_redis_admin.settings"`
  - Strict markers and strict configuration enabled
  - Branch coverage enabled: `--cov=redis_admin`, `--cov-report=term-missing`

### 5.2 Test Coverage Strategy (Target: 100%)
Expand `tests/` to achieve 100% line and branch coverage across `redis_admin`:
- **Sentinel Support**: Add tests for `get_sentinel()`, Sentinel master connection, and Sentinel slave connection using mock sentinels.
- **Data Types & Value Decoding**:
  - String, List, Set, Hash, ZSet fetching and representation.
  - Base64 encoding and decoding paths, including decode error handling.
  - JSON encoding and decoding paths, custom `JSON_MODULE`, and invalid JSON decode errors.
  - Crop size truncation logic for representation display.
- **Admin Views & Slicing**:
  - ModelAdmin changelist view, search queries (`startswith`, `endswith`, `contains`, `exact`), ordering, count calculation from keyspace info.
  - Readonly fields and change view object lookup.
- **Exceptions & Errors**:
  - `ResponseError` fallback in batch pipeline value fetching.
  - Unknown attribute error handling in `RedisMeta`, `RedisValue`, and `Queryset`.

### 5.3 Tox Matrix (`tox.ini`)
- Use `tox-uv` runner.
- Envs: `py310`, `py311`, `py312`, `py313`, `py314`, `pypy310`, `pypy311`.
- Quality envs: `lint`, `mypy`, `pyright`, `pyrefly`, `codespell`, `docs`, `coverage`.
- Combine coverage from test matrix cells and enforce `fail_under = 100`.

---

## 6. Documentation Modernization

### 6.1 Markdown Transition
- Convert `README.rst` to `README.md`. Ensure all badges and images use absolute URLs.
- Convert `docs/*.rst` to Markdown (`docs/*.md`) using `MyST-Parser`.
- Replace custom legacy Wolph theme with modern `Furo` theme.
- Configure `docs/conf.py` with `myst_parser`, `furo`, and project metadata.
- Add `.readthedocs.yaml` matching `python-utils`.

---

## 7. CI/CD Workflows

### 7.1 GitHub Actions (`.github/workflows/ci.yml`)
- Triggers on push to `master`, `develop`, and on pull requests.
- Jobs:
  1. `test`: matrix across Python 3.10-3.14 + PyPy, uploads `.coverage.<version>` artifact.
  2. `lint`: runs `ruff check` and `ruff format --check`.
  3. `type-check`: matrix across `mypy`, `pyright`, `pyrefly`.
  4. `codespell`: verifies spelling.
  5. `docs`: runs `sphinx-build -W -b html docs docs/_build/html`.
  6. `coverage`: downloads all coverage artifacts, combines them, and asserts 100% coverage via `coverage report --fail-under=100`.

### 7.2 GitHub Actions (`.github/workflows/publish.yml`)
- Trusted publishing workflow to PyPI on GitHub release publication.
