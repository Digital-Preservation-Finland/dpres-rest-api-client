from setuptools import find_packages, setup


setup(
    name='dpres-rest-api-client',
    packages=find_packages(include=["dpres_rest_api_client*"]),
    package_dir={
        "dpres_rest_api_client": "dpres_rest_api_client"
    },
    setup_requires=["setuptools_scm"],
    install_requires=[
        "click",
        "requests",
        "humanize",
        "tabulate",
        "tuspy"
    ],
    entry_points={
        "console_scripts": [
            "dpres-client = dpres_rest_api_client.cli:main"
        ]
    },
    python_requires=">=3.6",
    use_scm_version=True
)
