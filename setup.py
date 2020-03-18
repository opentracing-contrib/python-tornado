from setuptools import setup

version = open('VERSION').read()
setup(
    name='tornado_opentracing',
    version=version,
    url='https://github.com/opentracing-contrib/python-tornado/',
    download_url='https://github.com/opentracing-contrib/python-tornado/tarball/'+version,
    license='Apache License 2.0',
    author='Carlos Alberto Cortez',
    author_email='calberto.cortez@gmail.com',
    description='OpenTracing support for Tornado applications',
    long_description=open('README.rst').read(),
    packages=['tornado_opentracing'],
    platforms='any',
    install_requires=[
        'tornado',
        'opentracing>=2.1,<2.4',
        'wrapt',
    ],
    extras_require={
        'tests': [
            'flake8<4',
            'flake8-quotes',
            'pytest>=4.6.9',
            'pytest-cov',
            'mock',
            'tox',
        ],
    },
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
