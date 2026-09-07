"""Build the source distribution and run the test suite from it.

The sdist is what `pip install django-redis-admin` compiles when no wheel
matches, and it carries the tests for downstream packagers. Running the
suite from the unpacked archive proves the archive is complete, which is
exactly the check that would have caught the missing test settings module.

Usage:

    python scripts/check_sdist.py [workdir]

The working directory defaults to a fresh temporary directory.
"""

from __future__ import annotations

import glob
import pathlib
import subprocess
import sys
import tarfile
import tempfile


def build_sdist(workdir: pathlib.Path) -> pathlib.Path:
    dist: pathlib.Path = workdir / 'dist'
    subprocess.check_call(['uv', 'build', '--sdist', '--out-dir', str(dist)])
    archives: list[str] = glob.glob(str(dist / '*.tar.gz'))
    if len(archives) != 1:
        raise RuntimeError(f'Expected one sdist in {dist}, found {archives}')
    return pathlib.Path(archives[0])


def unpack(archive: pathlib.Path, workdir: pathlib.Path) -> pathlib.Path:
    source: pathlib.Path = workdir / 'src'
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter='data')
    roots: list[pathlib.Path] = [p for p in source.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(
            f'Expected one directory in {source}, found {roots}'
        )
    return roots[0]


def run_tests(source: pathlib.Path) -> int:
    subprocess.check_call(
        [
            'uv',
            'pip',
            'install',
            '--quiet',
            '--python',
            sys.executable,
            f'{source}[tests]',
        ]
    )
    return subprocess.call(
        [
            sys.executable,
            '-m',
            'pytest',
            '--no-cov',
            '-q',
            '-p',
            'no:cacheprovider',
        ],
        cwd=source,
    )


def main(argv: list[str]) -> int:
    if argv:
        workdir: pathlib.Path = pathlib.Path(argv[0])
        workdir.mkdir(parents=True, exist_ok=True)
        return run_tests(unpack(build_sdist(workdir), workdir))

    with tempfile.TemporaryDirectory() as tmp:
        return main([tmp])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
