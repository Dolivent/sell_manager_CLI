# scripts package

"""
Utility scripts for sell_manager_CLI.

These scripts are intended for developer and maintenance use. They are not
imported by the main application.

Scripts:
    compare_versions.py  — Compare MA values between backup and current code trees.
    clean_export.py      — Create a cleaned distribution copy of the project.

For temporary one-off scripts, use the `tmp/` folder at the project root.
"""

__all__ = [
    "compare_versions",
    "clean_export",
]
