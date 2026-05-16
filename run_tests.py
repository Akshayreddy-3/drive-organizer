#!/usr/bin/env python3
"""
run_tests.py - Test Runner for Drive Organizer

PURPOSE:
--------
Run all unit tests and display results.

USAGE:
------
    # Run all tests with summary
    python run_tests.py
    
    # Run with verbose output
    python run_tests.py -v
    
    # Run specific test file
    python -m unittest tests.test_file_grouper -v

TEST MODULES:
-------------
1. test_file_grouper - Tests for file name extraction and grouping
2. test_file_scanner - Tests for local file scanning
3. test_folder_navigator - Tests for Drive folder navigation

Author: Akshay Reddy
Date: 2026-02-03
"""

import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_all_tests(verbosity: int = 2) -> bool:
    """
    Discover and run all tests in the tests/ directory.
    
    Args:
        verbosity: 0=quiet, 1=brief, 2=detailed
        
    Returns:
        True if all tests passed, False otherwise
    """
    print("=" * 60)
    print("  🧪 Drive Organizer - Test Suite")
    print("=" * 60)
    print()
    
    # Discover all tests in the tests/ directory
    loader = unittest.TestLoader()
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    
    # Load all tests matching test_*.py pattern
    suite = loader.discover(test_dir, pattern='test_*.py')
    
    # Count tests
    test_count = suite.countTestCases()
    print(f"📋 Found {test_count} test(s)")
    print("-" * 60)
    print()
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 60)
    
    if result.wasSuccessful():
        print("  ✅ ALL TESTS PASSED")
    else:
        print("  ❌ SOME TESTS FAILED")
        
        # Show failure summary
        if result.failures:
            print(f"\n  Failures: {len(result.failures)}")
            for test, _ in result.failures:
                print(f"    - {test}")
        
        if result.errors:
            print(f"\n  Errors: {len(result.errors)}")
            for test, _ in result.errors:
                print(f"    - {test}")
    
    print("=" * 60)
    
    # Print stats
    print(f"\n📊 Results:")
    print(f"   • Tests run: {result.testsRun}")
    print(f"   • Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   • Failed: {len(result.failures)}")
    print(f"   • Errors: {len(result.errors)}")
    print()
    
    return result.wasSuccessful()


def main():
    """Main entry point."""
    # Check for verbose flag
    verbosity = 2 if '-v' in sys.argv or '--verbose' in sys.argv else 1
    
    # Run tests
    success = run_all_tests(verbosity)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
