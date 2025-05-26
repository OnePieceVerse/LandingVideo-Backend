#!/usr/bin/env python
import os
import sys
import unittest
import asyncio

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == "__main__":
    # Set event loop policy for asyncio tests to work properly
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Discover and run all tests in the src/tests directory
    test_suite = unittest.defaultTestLoader.discover('src/tests')
    test_runner = unittest.TextTestRunner(verbosity=2)
    test_runner.run(test_suite) 