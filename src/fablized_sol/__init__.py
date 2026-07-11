"""Super SOL package."""

from importlib.metadata import version as distribution_version
from typing import Final

__version__: Final = distribution_version("super-sol-harness")
