#!/usr/bin/env python3
"""Test runner that suppresses false-positive ResourceWarnings from SQLite."""

import sys
import unittest
import warnings

# Suppress ResourceWarnings from SQLite connections
# These are false positives - connections are properly closed in context managers
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed database")

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
