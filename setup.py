from setuptools import find_packages, setup

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('requirements.txt') as requirements_file:
    requirements = [item.strip() for item in requirements_file.readlines()]

with open('classifiers.txt') as classifiers_file:
    classifiers = [item.strip() for item in classifiers_file.readlines()]

setup_requirements = ['pytest-runner', 'flake8']

test_requirements = ['coverage', 'pytest', 'pytest-cov', 'pytest-mock']

setup(
    author='Eduardo Gonzalez Solares',
    author_email='eglez@ast.cam.ac.uk',
    classifiers=classifiers,
    description='Owl Pipeline Server Framework',
    entry_points={'console_scripts': ['owl-server=owl_server.cli:main', 'owl-migrate=owl_server.migrations.migrate:main']},
    install_requires=requirements,
    license='GNU General Public License v3',
    long_description=readme,
    include_package_data=True,
    keywords='owl, pipeline',
    name='owl-server',
    packages=find_packages(include=['owl_server*']),
#    data_files=[
#        ('conf', ['conf/pipeline.yaml', 'conf/scheduler.yaml', 'conf/log.yaml'])
#    ],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://gitlab.ast.cam.ac.uk/imaxt/owl-pipeline-server',
    version='0.4.0',
    zip_safe=False,
    python_requires='>=3.7',
)
