from setuptools import setup, find_packages

VERSION = '0.0.1'
DESCRIPTION = 'Package for developing a convenient project structure'

with open('README.md', 'r') as f:
    desc = f.read()

LONG_DESCRIPTION = desc

setup(
    name="ModuleManager",
    version=VERSION,
    author="Ivashka (Ivan Rakov)",
    author_email="<ivashka.2.r@gmail.com>",
    description=DESCRIPTION,
    packages=find_packages(),
    install_requires=[],
    keywords=['python', 'modules', 'queues', 'objects', 'classes', 'mm'],
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    platforms='any',
)
