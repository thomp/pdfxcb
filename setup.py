# Install at a nonstandard location:
# python setup.py develop --script-dir ~/bin --install-dir /home/thomp/.local/lib/python2.7/site-packages
# - use 'python -m site --user-site' to get local site-packages dir
from setuptools import setup, find_packages
setup(
    name = 'pdfxcb',
    description = "Split a PDF into separate PDF files",
    version = "0.1",
    entry_points={
        'console_scripts': [
            'pdfxcb=pdfxcb.pdfxcb:main'
        ]
    },
    # dependencies (a project's PyPI name)
    install_requires = ['PyPDF2'],
    packages = find_packages()
)

