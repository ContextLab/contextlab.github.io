#!/usr/bin/env python3
"""Pre-push check script for the Context Lab website.

Runs the same gates as .github/workflows/build-content.yml, in the same order:
lint, type check, validate data, rebuild all HTML pages, run the test suite.
This should be run before pushing to ensure consistency.

Keep the steps here in step with that workflow. A local check that passes what
CI rejects is worse than no local check, because it is trusted.
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def run_script(script_name: str) -> bool:
    """Run a Python script and return True if successful."""
    script_path = Path(__file__).parent / script_name
    print(f"\n{'=' * 50}")
    print(f"Running {script_name}...")
    print('=' * 50)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT
    )
    return result.returncode == 0


def run_command(label: str, cmd: list) -> bool:
    """Run a command from the project root and return True if successful.

    ruff and mypy read ruff.toml / mypy.ini there, so the invocation matches
    both the workflow and what a contributor types by hand.
    """
    print(f"\n{'=' * 50}")
    print(f"Running {label}...")
    print('=' * 50)

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    except FileNotFoundError:
        print(f"{cmd[0]} is not installed.")
        print("Install the build dependencies: pip install -r requirements-build.txt")
        return False
    return result.returncode == 0


def check_submodule() -> bool:
    """Check if lab-manual submodule is initialized."""
    lab_manual = Path(__file__).parent.parent / 'lab-manual' / 'lab_manual.tex'
    if not lab_manual.exists():
        print("\nWARNING: Lab-manual submodule not initialized.")
        print("Run: git submodule update --init")
        print("Some sync features will not work without it.\n")
        return False
    return True


def main():
    """Run all pre-push checks."""
    print("Context Lab Website Pre-Push Check")
    print("=" * 50)

    all_passed = True

    # Step 0: Check submodule
    check_submodule()  # Warning only, doesn't block

    # Step 1: Lint. Before the build, because a script that fails this is one
    # we should not be generating the site with.
    if not run_command('ruff (lint)', ['ruff', 'check']):
        print("\n*** Lint FAILED ***")
        print("Fix the findings, or apply the auto-fixable subset: ruff check --fix")
        all_passed = False

    # Step 2: Type check
    if all_passed:
        if not run_command('mypy (type check)', ['mypy']):
            print("\n*** Type check FAILED ***")
            print("Fix the type errors before pushing.")
            all_passed = False

    # Step 3: Validate data
    if all_passed:
        if not run_script('validate_data.py'):
            print("\n*** Data validation FAILED ***")
            print("Fix validation errors before pushing.")
            all_passed = False

    # Step 4: Build all pages
    if all_passed:
        if not run_script('build.py'):
            print("\n*** Build FAILED ***")
            print("Fix build errors before pushing.")
            all_passed = False

    # Step 5: Test suite
    if all_passed:
        if not run_command('pytest (test suite)',
                           [sys.executable, '-m', 'pytest', 'tests/', '-q']):
            print("\n*** Tests FAILED ***")
            print("Fix the failing tests before pushing.")
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
