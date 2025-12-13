#!/usr/bin/env python3
"""Pre-push check script for the Context Lab website.

Validates data files and rebuilds all HTML pages.
This should be run before pushing to ensure consistency.
"""
import subprocess
import sys
from pathlib import Path


def run_script(script_name: str) -> bool:
    """Run a Python script and return True if successful."""
    script_path = Path(__file__).parent / script_name
    print(f"\n{'=' * 50}")
    print(f"Running {script_name}...")
    print('=' * 50)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=Path(__file__).parent.parent
    )
    return result.returncode == 0


def main():
    """Run all pre-push checks."""
    print("Context Lab Website Pre-Push Check")
    print("=" * 50)

    all_passed = True

    # Step 1: Validate data
    if not run_script('validate_data.py'):
        print("\n*** Data validation FAILED ***")
        print("Fix validation errors before pushing.")
        all_passed = False

    # Step 2: Build all pages
    if all_passed:
        if not run_script('build.py'):
            print("\n*** Build FAILED ***")
            print("Fix build errors before pushing.")
            all_passed = False

    # Summary
    print("\n" + "=" * 50)
    print("Pre-Push Check Summary")
    print("=" * 50)

    if all_passed:
        print("All checks PASSED!")
        print("\nYou can safely push your changes.")
        sys.exit(0)
    else:
        print("Some checks FAILED!")
        print("\nPlease fix the issues before pushing.")
        sys.exit(1)


if __name__ == '__main__':
    main()
