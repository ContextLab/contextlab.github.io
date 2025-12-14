#!/usr/bin/env python3
"""
Build CV from LaTeX source to PDF and HTML.

This script:
1. Compiles JRM_CV.tex to PDF using XeLaTeX
2. Converts to HTML using custom LaTeX parser (extract_cv.py)
3. Cleans up temporary LaTeX build files
"""

import subprocess
import sys
from pathlib import Path

# Import the custom LaTeX parser
from extract_cv import extract_cv

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DOCUMENTS_DIR = PROJECT_ROOT / 'documents'
DATA_DIR = PROJECT_ROOT / 'data'
CSS_DIR = PROJECT_ROOT / 'css'
TEX_FILE = DOCUMENTS_DIR / 'JRM_CV.tex'
PDF_FILE = DOCUMENTS_DIR / 'JRM_CV.pdf'
HTML_FILE = DOCUMENTS_DIR / 'JRM_CV.html'

# LaTeX temporary file extensions to clean up
LATEX_TEMP_EXTENSIONS = [
    '.aux', '.log', '.out', '.toc', '.lof', '.lot', '.fls', '.fdb_latexmk',
    '.synctex.gz', '.bbl', '.blg', '.nav', '.snm', '.vrb',
    '.4ct', '.4tc', '.idv', '.lg', '.tmp', '.xdv', '.xref', '.dvi'
]


def run_command(cmd: list, cwd: Path = None, timeout: int = 120) -> tuple:
    """Run a command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, '', f'Command timed out after {timeout}s'
    except Exception as e:
        return False, '', str(e)


def compile_pdf() -> bool:
    """Compile LaTeX to PDF using XeLaTeX (run twice for references)."""
    print(f"Compiling {TEX_FILE.name} to PDF...")

    # Run xelatex twice for references
    for i in range(2):
        success, stdout, stderr = run_command(
            ['xelatex', '-interaction=nonstopmode', TEX_FILE.name],
            cwd=DOCUMENTS_DIR,
            timeout=120
        )
        if not success:
            print(f"XeLaTeX pass {i+1} failed:")
            print(stderr)
            # Check if PDF was still created despite warnings
            if not PDF_FILE.exists():
                return False

    if PDF_FILE.exists():
        size = PDF_FILE.stat().st_size
        print(f"PDF generated: {PDF_FILE} ({size:,} bytes)")
        return True
    else:
        print("PDF file not created")
        return False


def compile_html() -> bool:
    """Convert LaTeX to HTML using custom parser."""
    print(f"Converting {TEX_FILE.name} to HTML using custom parser...")

    success = extract_cv(TEX_FILE, HTML_FILE)

    if success and HTML_FILE.exists():
        size = HTML_FILE.stat().st_size
        print(f"HTML generated: {HTML_FILE} ({size:,} bytes)")
        return True
    else:
        print("HTML file not created")
        return False


def cleanup_temp_files():
    """Remove temporary LaTeX build files."""
    print("Cleaning up temporary files...")

    cleaned = 0
    for ext in LATEX_TEMP_EXTENSIONS:
        for f in DOCUMENTS_DIR.glob(f'*{ext}'):
            try:
                f.unlink()
                cleaned += 1
            except Exception as e:
                print(f"Could not remove {f}: {e}")

    print(f"Removed {cleaned} temporary files")


def validate_output() -> bool:
    """Validate that PDF and HTML were generated correctly."""
    print("\nValidating output...")

    errors = []

    # Check PDF
    if not PDF_FILE.exists():
        errors.append("PDF file not found")
    elif PDF_FILE.stat().st_size < 1000:
        errors.append(f"PDF file too small ({PDF_FILE.stat().st_size} bytes)")

    # Check HTML
    if not HTML_FILE.exists():
        errors.append("HTML file not found")
    else:
        with open(HTML_FILE, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check for key sections
        required_sections = ['Employment', 'Education', 'Publications']
        for section in required_sections:
            if section not in html_content:
                errors.append(f"HTML missing section: {section}")

        # Check for download button
        if 'cv-download-bar' not in html_content:
            errors.append("HTML missing PDF download button")

        # Check for CSS link
        if 'cv.css' not in html_content:
            errors.append("HTML missing CSS link")

    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("Validation passed!")
    print(f"  PDF: {PDF_FILE} ({PDF_FILE.stat().st_size:,} bytes)")
    print(f"  HTML: {HTML_FILE} ({HTML_FILE.stat().st_size:,} bytes)")
    return True


def build_cv() -> bool:
    """Main build function."""
    print("=" * 60)
    print("Building CV from LaTeX source")
    print("=" * 60)

    # Check source file exists
    if not TEX_FILE.exists():
        print(f"Error: Source file not found: {TEX_FILE}")
        return False

    # Compile PDF
    if not compile_pdf():
        print("Failed to compile PDF")
        return False

    # Compile HTML using custom parser
    if not compile_html():
        print("Failed to generate HTML")
        return False

    # Clean up
    cleanup_temp_files()

    # Validate
    if not validate_output():
        return False

    print("\n" + "=" * 60)
    print("CV build completed successfully!")
    print("=" * 60)
    return True


if __name__ == '__main__':
    success = build_cv()
    sys.exit(0 if success else 1)
