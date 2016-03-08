from setuptools import setup
setup(
    name = "ghpick",
    version = "1.0.1",
    packages = ["ghpick"],
    install_requires = ['requests>=2.7.0'],
    tests_require = ['vcrpy>=1.6.0','mock>=1.0.1','contextlib2>=0.4.0'],

    # metadata for upload to PyPI
    author = "Ryan Parr",
    author_email = "whiskeyriver",
    description = "Perform cherry-pick patching with the Github API",
    license = "MIT",
    keywords = "github githubapi cherry pick cherry-pick cherrypick merge",
    url = "http://github.com/whiskeyriver/ghpick"
)
