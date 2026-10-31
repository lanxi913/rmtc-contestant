from setuptools import find_packages, setup


package_name = "rmtc_contestant"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Wang Ye",
    maintainer_email="276544627+lanxi913@users.noreply.github.com",
    description="RMTC contestant ROS 2 package skeleton and protocol core.",
    license="Apache-2.0",
    entry_points={"console_scripts": ["contestant = rmtc_contestant.node:main"]},
)
