import os
import pkgutil

# Get the directory containing this __init__.py file
package_dir = os.path.dirname(__file__)

# Discover all modules in the skills directory
__all__ = [
    name
    for _, name, _ in pkgutil.iter_modules([package_dir])
    if not name.startswith("_") and not name == "base"
]
