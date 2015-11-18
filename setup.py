import txgpio
from setuptools import setup, find_packages


setup(
    name='txgpio',
    version=txgpio.__version__,
    description='Twisted-based asynchronous library for using GPIO.',
    packages=find_packages(),
    py_modules=['txgpio'],
)
