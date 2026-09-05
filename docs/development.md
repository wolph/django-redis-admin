# Development

The project uses [uv](https://docs.astral.sh/uv/) for environments, ruff for
linting and formatting, three type checkers, pytest with a 100% coverage gate,
and tox to run the same matrix locally that CI runs.

## Setting up

```bash
git clone https://github.com/wolph/django-redis-admin.git
cd django-redis-admin
uv sync
uv run lefthook install
```

`uv sync` installs the package with its test, docs and development groups.
`lefthook install` adds the git hooks: ruff and codespell on staged files
before each commit, and ruff, mypy and a fast test run before each push.

The tests start their own `redis-server` on a free port, so a Redis binary
has to be on `PATH`. On macOS `brew install redis` provides it, on Debian and
Ubuntu `apt install redis-server` does.

## Running the checks

```bash
uv run pytest                 # tests, 100% line and branch coverage required
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
uv run mypy                   # type check, django-stubs plugin
uv run basedpyright           # type check
uv run pyrefly check          # type check, strict preset
uv run codespell              # spelling
```

tox runs the same commands in isolated environments and adds the version
matrix:

```bash
uvx --with tox-uv tox -p auto   # everything CI runs, in parallel
uvx --with tox-uv tox -m check  # lint, type checkers and codespell only
uvx --with tox-uv tox -m test   # Python 3.10 to 3.14 and PyPy 3.10 and 3.11
uvx --with tox-uv tox -m compat # pinned Django 4.2, 5.2, 6.0 and 6.1
uvx --with tox-uv tox -e docs   # build the documentation with warnings as errors
```

Missing interpreters are provisioned by tox-uv, so the full matrix runs on a
machine with only one Python installed.

## Coverage on PyPy

The PyPy environments run pytest with `--no-cov`. Coverage instrumentation
makes Django's admin autodiscover fail on PyPy with `ValueError: site must
subclass AdminSite`, an upstream incompatibility tracked as
[Django ticket 35418](https://code.djangoproject.com/ticket/35418). The
CPython cells collect coverage, CI combines their data files, and the
combined report has to reach 100%. Nothing runs on PyPy that does not also
run on CPython, so the gate loses nothing.

## Django compatibility

The default test cells resolve the newest Django that supports each Python.
The `compat` label pins the oldest supported series and the current releases
instead, so a compatibility break fails in CI rather than in a user's project:

| Environment | Python | Django |
| --- | --- | --- |
| `py312-django42` | 3.12 | 4.2 |
| `py313-django52` | 3.13 | 5.2 |
| `py314-django60` | 3.14 | 6.0 |
| `py314-django61` | 3.14 | 6.1 |

## Documentation

The docs are Markdown, rendered by Sphinx with MyST-Parser and the Furo
theme. Build them locally with:

```bash
uvx --with tox-uv tox -e docs
open docs/_build/html/index.html
```

The screenshots in `docs/_static/` come from the {doc}`demo` project,
captured at 1280 pixels wide in a light colour scheme. Re-run the demo and
recapture them when the admin changes.

## Releasing

Releases are tagged on `master`. A `v*` tag triggers the publish workflow,
which builds the distributions with `uv build` and uploads them to PyPI with
Trusted Publishing, so no token is stored anywhere. Bump the version with
`uv version --bump patch` or `minor`, commit, tag, and push with
`--follow-tags`.
