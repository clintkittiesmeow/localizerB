from setuptools import setup


def readme():
    with open('README.md') as f:
        return f.read()

setup(name='localizer',
      version='0.1',
      description='Signal Localizer',
      long_description=readme(),
      url='https://github.com/elBradford/localizer',
      author='Bradford',
      packages=['localizer'],
      install_requires=[
          'RPi.GPIO',
          'xtermcolor',
      ],
      entry_points={
          'console_scripts': ['localizer=localizer.main:main'],
      },
      zip_safe=False)
