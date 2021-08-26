from setuptools import find_packages, setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("requirements.txt") as requirements_file:
    requirements = [item.strip() for item in requirements_file.readlines()]

with open("classifiers.txt") as classifiers_file:
    classifiers = [item.strip() for item in classifiers_file.readlines()]

setup_requirements = ["pytest-runner", "flake8"]

test_requirements = ["coverage", "pytest", "pytest-cov", "pytest-mock"]

project_urls = {
  'Documentation': 'https://eddienko.github.io/owl-pipeline/',
  'Tracker': 'https://github.com/eddienko/owl-pipeline-server/issues',
}

setup(
    author="Eduardo Gonzalez Solares",
    author_email="e.gonzalezsolares@gmail.com",
    classifiers=classifiers,
    description="Owl Pipeline Server Framework",
    entry_points={
        "console_scripts": [
            "owl-server=owl_server.cli:main",
            "owl-migrate=owl_server.migrations.migrate:main",
        ]
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme,
    keywords="owl, pipeline, dask, kubernetes, python",
    name="owl-pipeline-server",
    packages=find_packages(include=["owl_server*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/eddienko/owl-pipeline-server",
    project_urls=project_urls,
    version="0.8.1",
    zip_safe=False,
    python_requires=">=3.8",
)
