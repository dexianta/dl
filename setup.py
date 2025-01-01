from setuptools import setup, find_packages

setup(
    name="dl",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[],  # Add dependencies here, e.g., ["requests"]
    entry_points={
        "console_scripts": [
            "dl=dl.main:main",
        ],
    },
    author="Dexian Tang",
    author_email="dxe.tang@gmail.com",
    description="A simple RAG tool",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/dexianta/dl",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.10",
)
