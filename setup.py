#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages


# Not all systems use utf8 encoding by default, this works around that issue
if sys.version_info > (3,):
    from functools import partial
    open = partial(open, encoding='utf8')


# To prevent importing about and thereby breaking the coverage info we use this
# exec hack
about = {}
with open('redis_admin/__about__.py') as fp:
    exec(fp.read(), about)


if sys.argv[-1] == 'info':
    for k, v in about.items():
        print('%s: %s' % (k, v))
    sys.exit()


if os.path.isfile('README.rst'):
    with open('README.rst') as fh:
        readme = fh.read()
else:
    readme = \
        f'''See http://pypi.python.org/pypi/{about['__package_name__']}/'''


if __name__ == '__main__':
    setup(
        name=about['__package_name__'],
        version=about['__version__'],
        author=about['__author__'],
        author_email=about['__email__'],
        description=about['__description__'],
        url=about['__url__'],
        license=about['__license__'],
        keywords=about['__title__'],
        packages=find_packages(exclude=['docs']),
        long_description=readme,
        include_package_data=True,
        install_requires=[
            'redis',
            'django',
        ],
        setup_requires=['setuptools'],
        zip_safe=False,
        extras_require={
            'docs': [
                'sphinx>=1.7.4',
            ],
            'tests': [
                'pytest',
            ],
        },
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Natural Language :: English',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
        ],
    )
