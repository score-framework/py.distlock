import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()

setup(
    name='score.distlock',
    version='0.1',
    description='Mutex for distributed operations with The SCORE Framework',
    long_description=README,
    author='strg.at',
    author_email='score@strg.at',
    url='http://score-framework.org',
    keywords='score framework mutex synchronization',
    packages=['score.distlock'],
    install_requires=[
        'score.init >= 0.1',
        'SQLAlchemy >= 0.9',
    ],
)
