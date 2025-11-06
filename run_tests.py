#!/usr/bin/env python3
"""
Run all USIF tests
Comprehensive test runner for the modular USIF package
"""

import sys
import unittest
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))


def discover_and_run_tests():
    """Discover and run all tests"""
    # Discover tests in current directory
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = unittest.TestSuite()
    
    # Add tests from test files
    test_files = [
        'test_all.py',
        'test_property.py',
        'test_suit.py',
    ]
    
    # Add tests from tests directory if it exists
    tests_dir = start_dir / 'tests'
    if tests_dir.exists():
        suite.addTests(loader.discover(str(tests_dir), pattern='test_*.py'))
    
    # Add tests from individual test files
    for test_file in test_files:
        test_path = start_dir / test_file
        if test_path.exists():
            try:
                # Try to load tests from the file
                module_name = test_file.replace('.py', '')
                spec = __import__(module_name, fromlist=[''])
                suite.addTests(loader.loadTestsFromModule(spec))
            except Exception as e:
                print(f"Warning: Could not load tests from {test_file}: {e}")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 70)
    print("USIF Modular Package Test Suite")
    print("=" * 70)
    print()
    
    success = discover_and_run_tests()
    
    print()
    print("=" * 70)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 70)
    
    sys.exit(0 if success else 1)

