import os
import sys

# Ensure the package src directory is on sys.path so tests can import `sellmanagement`
TESTS_DIR = os.path.dirname(__file__)
PROJECT_SRC = os.path.abspath(os.path.join(TESTS_DIR, '..', 'src'))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)


