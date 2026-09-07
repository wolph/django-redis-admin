# Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize `django-redis-admin` to full parity with `python-utils`, including `uv_build` packaging, `ruff` linting and formatting, strict type checking (`mypy`, `basedpyright`, `pyrefly`), 100% test coverage, Markdown documentation with Furo, and GitHub Actions CI.

**Architecture:** Replace legacy setuptools packaging with `pyproject.toml` and `uv_build`. Enforce code quality using `ruff.toml` and triple strict type checkers. Expand test suite with mock Sentinel and Redis type fixtures to reach 100% branch and line coverage. Convert Sphinx docs to Markdown via MyST-Parser and Furo. Configure full CI and Tox matrices.

**Tech Stack:** Python 3.10+, Django 4.2+, Redis, uv, uv_build, ruff, mypy, basedpyright, pyrefly, pytest, pytest-cov, pytest-django, tox-uv, Sphinx, Furo, MyST-Parser, GitHub Actions.

---

### Task 1: Build System and Packaging (`pyproject.toml`)

**Files:**
- Create: `pyproject.toml`
- Create: `redis_admin/py.typed`
- Modify: `setup.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create `redis_admin/py.typed` marker**

Create an empty `redis_admin/py.typed` file to declare PEP 561 compliance.

- [ ] **Step 2: Create `pyproject.toml`**

Define `[build-system]`, `[project]`, `[project.urls]`, `[dependency-groups]`, `[tool.uv]`, and basic tool tables.

```toml
[build-system]
requires = ['uv_build>=0.11,<0.13']
build-backend = 'uv_build'

[tool.uv.build-backend]
module-root = ''
module-name = 'redis_admin'
source-include = ['tests/**/*.py', 'tox.ini']

[project]
name = 'django-redis-admin'
version = "0.3.0"
description = 'A Django Admin interface for Redis servers with optional Redis Sentinel support'
readme = 'README.md'
requires-python = '>=3.10'
license = 'BSD-3-Clause'
license-files = ['LICENSE']
authors = [{ name = 'Rick van Hattem', email = 'wolph@wol.ph' }]
keywords = ['redis', 'django', 'admin', 'sentinel']
classifiers = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Web Environment',
    'Framework :: Django',
    'Framework :: Django :: 4.2',
    'Framework :: Django :: 5.0',
    'Framework :: Django :: 5.1',
    'Framework :: Django :: 5.2',
    'Intended Audience :: Developers',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    'Programming Language :: Python :: 3.14',
    'Programming Language :: Python :: Implementation :: CPython',
    'Programming Language :: Python :: Implementation :: PyPy',
    'Typing :: Typed',
]
dependencies = [
    'redis>=4.0.0',
    'django>=4.2',
]

[project.urls]
Homepage = 'https://github.com/WoLpH/django-redis-admin'
Documentation = 'https://django-redis-admin.readthedocs.io/'
Repository = 'https://github.com/WoLpH/django-redis-admin'
Changelog = 'https://github.com/WoLpH/django-redis-admin/releases'

[project.optional-dependencies]
docs = ['sphinx', 'furo', 'myst-parser']
tests = [
    'pytest',
    'pytest-cov',
    'pytest-django',
    'fakeredis',
]

[dependency-groups]
docs = ['sphinx', 'furo', 'myst-parser']
test = [
    'pytest',
    'pytest-cov',
    'pytest-django',
    'fakeredis',
]
dev = [
    'ruff',
    'mypy',
    'basedpyright',
    'pyrefly',
    'codespell',
    'django-stubs',
    'types-redis',
    'lefthook',
    { include-group = 'test' },
    { include-group = 'docs' },
]
tox = ['tox>=4', 'tox-uv>=1', 'tox-gh-actions']

[tool.uv]
exclude-newer = "14 days"
```

- [ ] **Step 3: Update `setup.py` as thin backward-compatible shim**

```python
import setuptools

if __name__ == '__main__':
    setuptools.setup()
```

- [ ] **Step 4: Verify package builds with uv**

Run: `uv build`
Expected: Successfully built wheel and sdist in `dist/`.

- [ ] **Step 5: Commit build configuration**

```bash
git add pyproject.toml redis_admin/py.typed setup.py .gitignore
git commit -m "build: migrate build system to uv_build and pyproject.toml"
```

---

### Task 2: Code Style, Formatting and Linting (Ruff and Codespell)

**Files:**
- Create: `ruff.toml`
- Modify: `pyproject.toml`
- Modify: `redis_admin/models.py`
- Modify: `redis_admin/client.py`
- Modify: `redis_admin/admin.py`
- Modify: `redis_admin/settings.py`
- Modify: `test_redis_admin/manage.py`
- Modify: `test_redis_admin/settings.py`

- [ ] **Step 1: Create `ruff.toml`**

Adopt `python-utils` ruff configuration:

```toml
target-version = 'py310'

exclude = [
    '.venv',
    '.tox',
]

line-length = 79
extend-exclude = ['*.md']

[lint]
ignore = [
    'A001',
    'A002',
    'A003',
    'B023',
    'B024',
    'D205',
    'D212',
    'RET505',
    'TRY003',
    'RET507',
    'C405',
    'C406',
    'C408',
    'SIM114',
    'RET506',
    'Q001',
    'Q002',
    'FA100',
    'COM812',
    'ISC001',
    'SIM108',
    'RUF100',
    'D100',
    'D101',
    'D102',
    'D103',
    'D104',
    'D105',
    'D106',
    'D107',
]

select = [
    'A',
    'ASYNC',
    'B',
    'C4',
    'C90',
    'COM',
    'D',
    'E',
    'F',
    'FA',
    'I',
    'ICN',
    'INP',
    'ISC',
    'N',
    'PERF',
    'PIE',
    'Q',
    'RET',
    'RUF',
    'SIM',
    'T20',
    'TD',
    'TRY',
    'UP',
]

[lint.per-file-ignores]
'*tests/*' = ['INP001', 'T201', 'T203', 'ASYNC109', 'B007']
'test_redis_admin/*' = ['INP001', 'T201']
'docs/*' = ['INP001', 'E501']

[lint.pydocstyle]
convention = 'google'
ignore-decorators = [
    'typing.overload',
    'typing.override',
]

[lint.isort]
case-sensitive = true
combine-as-imports = true
force-wrap-aliases = true

[lint.flake8-quotes]
docstring-quotes = 'single'
inline-quotes = 'single'
multiline-quotes = 'single'

[format]
quote-style = 'single'
line-ending = 'lf'
```

- [ ] **Step 2: Add codespell configuration to `pyproject.toml`**

```toml
[tool.codespell]
skip = '*.lock,*.svg,*.egg-info,./.git,./.tox,./.venv,./.ruff_cache,./.mypy_cache,./.pytest_cache,./build,./dist,./htmlcov,./docs/_build,*/__pycache__'
check-hidden = true
```

- [ ] **Step 3: Fix ruff lint errors and formatting in source code**

Fix unused variables (`v0`, `v1`, `v2`), replace `%` string formats with f-strings, remove unnecessary prints, sort imports, and apply single-quote formatting.

- [ ] **Step 4: Verify ruff and codespell pass cleanly**

Run: `uv run --with ruff ruff check .`
Run: `uv run --with ruff ruff format --check .`
Run: `uv run --with codespell codespell`
Expected: 0 errors reported by all tools.

- [ ] **Step 5: Commit linting and formatting changes**

```bash
git add ruff.toml pyproject.toml redis_admin/ test_redis_admin/ tests/
git commit -m "style: configure ruff and codespell and format codebase"
```

---

### Task 3: Strict Static Type Checking (`mypy`, `basedpyright`, `pyrefly`)

**Files:**
- Modify: `pyproject.toml`
- Modify: `redis_admin/models.py`
- Modify: `redis_admin/client.py`
- Modify: `redis_admin/admin.py`
- Modify: `redis_admin/settings.py`

- [ ] **Step 1: Configure type checkers in `pyproject.toml`**

```toml
[tool.mypy]
python_version = '3.10'
strict = true
check_untyped_defs = true
files = ['redis_admin', 'tests']
plugins = ['mypy_django_plugin.main']

[[tool.mypy.overrides]]
module = 'tests.*'
disallow_untyped_defs = false

[tool.django-stubs]
django_settings_module = 'test_redis_admin.settings'

[tool.pyright]
typeCheckingMode = 'strict'
pythonVersion = '3.10'
include = ['redis_admin', 'tests']
exclude = ['**/__pycache__', '.tox', '.venv', 'build', 'dist', 'docs']
reportMissingTypeStubs = false

[tool.pyrefly]
project-includes = ['redis_admin', 'tests']
project-excludes = ['**/__pycache__', '.tox', '.venv']
python-version = '3.10'
```

- [ ] **Step 2: Refactor `redis_admin/models.py` for strict typing**

Add explicit type annotations to all model fields (`models.CharField`, `models.DateTimeField`, etc.), annotate `RedisValue.TYPES`, fix `RedisSet.value` return type to `typing.Set[typing.Any]`, and annotate dynamic server models safely without `globals()` abuse.

- [ ] **Step 3: Refactor `redis_admin/client.py` and `redis_admin/admin.py` for strict typing**

Add proper type annotations to `masters` and `slaves` dicts, annotate all parameters and return values in `client.py`, and type `Queryset` properties (`self.slave`, `self.master`, `self.filters`, `self.slice`).

- [ ] **Step 4: Run type checkers to verify 0 errors**

Run: `uv run --with mypy,django-stubs,types-redis mypy`
Run: `uv run --with basedpyright basedpyright`
Run: `uv run --with pyrefly pyrefly check`
Expected: All three type checkers exit with code 0.

- [ ] **Step 5: Commit strict typing changes**

```bash
git add pyproject.toml redis_admin/
git commit -m "types: enable strict mypy, basedpyright, and pyrefly type checking"
```

---

### Task 4: Comprehensive Test Suite and 100% Coverage

**Files:**
- Modify: `pyproject.toml`
- Modify: `pytest.ini`
- Modify: `tests/conftest.py`
- Modify: `tests/test_exclusion.py`
- Create: `tests/test_client.py`
- Create: `tests/test_models.py`
- Create: `tests/test_admin.py`

- [ ] **Step 1: Configure pytest and coverage in `pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ['tests']
python_files = ['test_*.py']
addopts = [
    '--strict-config',
    '--strict-markers',
    '-ra',
    '--cov=redis_admin',
    '--cov-report=term-missing',
]
django_settings_module = 'test_redis_admin.settings'

[tool.coverage.run]
branch = true
parallel = true
source = ['redis_admin']

[tool.coverage.paths]
source = ['redis_admin', '*/redis_admin']

[tool.coverage.report]
fail_under = 100
show_missing = true
exclude_also = [
    'pragma: no cover',
    'if typing.TYPE_CHECKING:',
    'if __name__ == .__main__.:',
    'raise NotImplementedError',
]
```

- [ ] **Step 2: Write tests for `client.py` (Sentinel and Standalone connections)**

In `tests/test_client.py`:
- Test `get_sentinel()` with custom `SENTINEL_OPTIONS` and default timeout.
- Test `get_master()` with sentinel service name.
- Test `get_slave()` with sentinel service name.
- Test `get_master()` and `get_slave()` with master/slave subdictionaries.
- Test caching in `client.masters` and `client.slaves`.

- [ ] **Step 3: Write tests for `models.py` (all Redis data types, base64, json, cropping)**

In `tests/test_models.py`:
- Test `RedisString`, `RedisList`, `RedisSet`, `RedisHash`, `RedisZSet` value retrieval and decoding.
- Test `BASE64_KEY_RE` base64 decoding and invalid base64 fallback.
- Test `JSON_KEY_RE` json decoding and invalid json fallback.
- Test `get_cropped_value()` truncation and repr formatting.
- Test `ttl` and `idle` property calculations.
- Test `RedisMeta.get_field()` and `__getattr__` error handling.
- Test `RedisValue.__getattr__` error handling.

- [ ] **Step 4: Write tests for `admin.py` (queries, sorting, pipelines, response errors)**

In `tests/test_admin.py`:
- Test `Queryset.count()` and `Queryset.__len__()` without filters and with filters.
- Test `Queryset.filter()` with `exact`, `startswith`, `endswith`, `contains`, and unsupported filters.
- Test `Queryset` slicing with integer indices and slices.
- Test `Queryset.get()` with existing and non-existing keys.
- Test `Queryset.__iter__()` pipeline `ResponseError` fallback to direct slave fetching.
- Test `RedisAdmin.get_queryset()`, readonly fields, and admin changelist views.

- [ ] **Step 5: Run full test suite and verify 100% line and branch coverage**

Run: `uv run --with pytest,pytest-cov,pytest-django,fakeredis pytest --cov=redis_admin --cov-fail-under=100`
Expected: All tests pass, 100% coverage achieved, exit code 0.

- [ ] **Step 6: Commit test suite and coverage configuration**

```bash
git add pyproject.toml pytest.ini tests/
git commit -m "test: add comprehensive test suite achieving 100% branch coverage"
```

---

### Task 5: Documentation Modernization (Markdown, MyST, Furo)

**Files:**
- Create: `README.md`
- Remove: `README.rst`
- Create: `.readthedocs.yaml`
- Modify: `docs/conf.py`
- Modify: `docs/index.md` (convert from `docs/index.rst`)
- Modify: `docs/requirements.txt`
- Remove: `docs/_theme/`

- [ ] **Step 1: Convert `README.rst` to `README.md`**

Translate all documentation, installation steps, configuration guides, and exclusion examples to clean GitHub-flavored Markdown. Ensure all images use absolute URLs. Remove `README.rst`.

- [ ] **Step 2: Update `docs/conf.py` for Furo and MyST-Parser**

Configure `extensions = ['myst_parser', 'sphinx.ext.autodoc', 'sphinx.ext.napoleon', 'sphinx.ext.viewcode']`, `html_theme = 'furo'`, remove custom theme directory, and set documentation metadata.

- [ ] **Step 3: Convert `docs/*.rst` to Markdown**

Convert `docs/index.rst`, `docs/usage.rst`, `docs/redis_admin.rst` to `.md` format. Remove obsolete `.rst` files.

- [ ] **Step 4: Create `.readthedocs.yaml`**

```yaml
version: 2

build:
  os: ubuntu-24.04
  tools:
    python: '3.12'

python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
```

- [ ] **Step 5: Verify docs build cleanly**

Run: `uv run --with sphinx,furo,myst-parser sphinx-build -W -b html docs docs/_build/html`
Expected: Docs build cleanly with 0 warnings.

- [ ] **Step 6: Commit documentation modernization**

```bash
git add README.md docs/ .readthedocs.yaml
git rm README.rst docs/_theme/ -r -f --ignore-unmatch
git commit -m "docs: modernize documentation with Markdown, MyST-Parser, and Furo theme"
```

---

### Task 6: CI/CD Workflows, Tox Matrix, and Pre-commit Hooks

**Files:**
- Create: `tox.ini`
- Create: `lefthook.yml`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/publish.yml`

- [ ] **Step 1: Create `tox.ini`**

```ini
[tox]
requires =
    tox>=4
    tox-uv>=1
skip_missing_interpreters = true
env_list =
    py{310,311,312,313,314}
    pypy{310,311}
    lint
    mypy
    pyright
    pyrefly
    codespell
    docs
    coverage
labels =
    test = py{310,311,312,313,314}, pypy{310,311}
    check = lint, mypy, pyright, pyrefly, codespell

[gh-actions]
python =
    3.10: py310
    3.11: py311
    3.12: py312
    3.13: py313
    3.14: py314
    pypy-3.10: pypy310
    pypy-3.11: pypy311

[testenv]
runner = uv-venv-lock-runner
extras = tests
uv_sync_flags = --no-default-groups
uv_sync_locked = false
pass_env = COVERAGE_FILE
commands = pytest --cov-fail-under=0 {posargs}

[testenv:lint]
runner = uv-venv-runner
dependency_groups = dev
commands =
    ruff check .
    ruff format --check .

[testenv:mypy]
runner = uv-venv-runner
dependency_groups = dev
commands = mypy

[testenv:pyright]
runner = uv-venv-runner
dependency_groups = dev
commands = basedpyright

[testenv:pyrefly]
runner = uv-venv-runner
dependency_groups = dev
commands = pyrefly check

[testenv:codespell]
runner = uv-venv-runner
dependency_groups = dev
commands = codespell

[testenv:docs]
runner = uv-venv-runner
extras = docs
commands = sphinx-build -W -b html docs docs/_build/html

[testenv:coverage]
runner = uv-venv-lock-runner
extras = tests
uv_sync_flags = --no-default-groups
uv_sync_locked = false
commands =
    coverage erase
    pytest --cov=redis_admin --cov-report=term-missing --cov-fail-under=100
```

- [ ] **Step 2: Create `lefthook.yml`**

```yaml
pre-commit:
  parallel: true
  commands:
    ruff-check:
      glob: "*.py"
      run: uv run ruff check --fix {staged_files}
      stage_fixed: true
    ruff-format:
      glob: "*.py"
      run: uv run ruff format {staged_files}
      stage_fixed: true
    codespell:
      run: uv run codespell
    typecheck:
      run: uv run mypy
```

- [ ] **Step 3: Create `.github/workflows/ci.yml`**

Adopt `python-utils` CI workflow with matrix across Python 3.10-3.14 + PyPy, individual checks (lint, mypy, pyright, pyrefly, codespell, docs), and coverage combine enforcing 100% coverage.

- [ ] **Step 4: Create `.github/workflows/publish.yml`**

Trusted publishing workflow deploying distributions built with `uv build` to PyPI upon GitHub release publication.

- [ ] **Step 5: Run CI validation commands locally**

Verify `ruff check`, `ruff format --check`, `mypy`, `basedpyright`, `pyrefly check`, `codespell`, and `pytest --cov=redis_admin --cov-fail-under=100`.

- [ ] **Step 6: Commit CI/CD and automation files**

```bash
git add tox.ini lefthook.yml .github/workflows/ci.yml .github/workflows/publish.yml
git commit -m "ci: add GitHub Actions workflows, tox matrix, and lefthook configuration"
```
