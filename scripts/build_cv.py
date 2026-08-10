#!/usr/bin/env python3
"""
Build CV from LaTeX source to PDF and HTML.

This script:
1. Compiles JRM_CV.tex to PDF using XeLaTeX
2. Converts to HTML using custom LaTeX parser (extract_cv.py)
3. Cleans up temporary LaTeX build files
"""

import re
import subprocess
import sys
import zlib
from pathlib import Path
from typing import List, Optional, Tuple

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
LOG_FILE = DOCUMENTS_DIR / 'JRM_CV.log'
MISSFONT_FILE = DOCUMENTS_DIR / 'missfont.log'

# LaTeX temporary file extensions to clean up
LATEX_TEMP_EXTENSIONS = [
    '.aux', '.log', '.out', '.toc', '.lof', '.lot', '.fls', '.fdb_latexmk',
    '.synctex.gz', '.bbl', '.blg', '.nav', '.snm', '.vrb',
    '.4ct', '.4tc', '.idv', '.lg', '.tmp', '.xdv', '.xref', '.dvi'
]

# Guardrail thresholds, measured against the real CV. A healthy build is
# 14 pages / ~108,000 bytes / ~1,450 text-drawing operators. The nullfont
# failure mode produces a structurally valid but completely blank PDF at
# 10 pages / ~4,000 bytes / ~10 operators -- while still exiting 0. Note
# that the page count alone does NOT separate the two cases, which is why
# the size and text-operator floors matter.
# The byte floor is set above the ~75,000 bytes a 4-page CV weighs (embedded
# fonts dominate the file size), so that it catches truncation rather than
# only the extreme blank case.
MIN_PDF_BYTES = 90_000
MIN_PDF_PAGES = 12
MIN_TEXT_OPERATORS = 500

# Log signatures that mean glyphs were silently dropped. When LaTeX cannot
# resolve a font it substitutes `nullfont`, which emits no glyphs at all, so
# the run reports success and writes a blank PDF.
#
# These patterns are deliberately narrow. A healthy build's log contains
# benign strings like "Package pdftexcmds Info: \pdfdraftmode not found." and
# "LaTeX Font Info: Font shape `TU/Monaco(0)/m/n' will be ... used instead",
# so matching on bare "not found" or "Font shape" would fail every good build.
FONT_FAILURE_PATTERNS = [
    (r'in font nullfont', 'font resolved to nullfont, so no glyphs were drawn'),
    (r'^! Font .*not (?:loadable|found)', 'a font could not be loaded'),
    (r'mktextfm', 'legacy TFM font lookup (wrong engine -- this needs xelatex)'),
    (r'cannot-use-pdftex', 'fontspec requires xelatex or lualatex, not pdflatex'),
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


def iter_pdf_streams(data: bytes):
    """Yield the decoded bytes of every stream in a PDF.

    Streams are decompressed with an incremental decompressor rather than by
    slicing up to the next `endstream`: compressed data can itself contain
    the bytes "endstream", which truncates the slice and silently drops the
    stream. On the real CV that mis-parsed 29 of 59 streams.
    """
    for match in re.finditer(rb'stream\r?\n', data):
        start = match.end()
        chunk = data[start:]

        try:
            yield zlib.decompressobj().decompress(chunk)
            continue
        except zlib.error:
            pass

        # Not a flate stream. Fall back to the raw bytes up to `endstream`,
        # and only trust them if they look like an uncompressed content
        # stream rather than image or font data.
        end = data.find(b'endstream', start)
        if end != -1 and b'BT' in data[start:end]:
            yield data[start:end]


def count_pdf_text_operators(pdf_path: Path) -> int:
    """Count text-drawing operators across a PDF's content streams.

    Uses only the standard library. This is the check that separates a real
    CV from a blank one: a PDF whose fonts failed to resolve is structurally
    valid and has a plausible page count, but draws almost no text.
    """
    data = pdf_path.read_bytes()
    # Tj and TJ show text; ' and " show text and move to the next line.
    operator = re.compile(rb"(?:\bT[jJ]\b|[)\]]\s*['\"])")
    return sum(len(operator.findall(stream)) for stream in iter_pdf_streams(data))


def count_pdf_pages(pdf_path: Path) -> int:
    """Count page objects in a PDF.

    Read from the PDF itself rather than from the LaTeX log, so that a log
    and a PDF that disagree -- the signature of a stale file -- cannot pass.
    Page objects may live in compressed object streams, so the search covers
    decoded streams as well as the raw bytes.
    """
    data = pdf_path.read_bytes()
    page = re.compile(rb'/Type\s*/Page(?![sA-Za-z])')

    total = len(page.findall(data))
    for stream in iter_pdf_streams(data):
        total += len(page.findall(stream))

    return total


def has_valid_pdf_trailer(pdf_path: Path) -> bool:
    """Check that a PDF is not truncated.

    A file cut short can still contain every content stream -- and so pass a
    size and text check -- while being unopenable, because the cross-reference
    table and trailer live at the end.
    """
    data = pdf_path.read_bytes()
    if not data.startswith(b'%PDF-'):
        return False

    tail = data[-2048:]
    return b'startxref' in tail and b'%%EOF' in tail


def parse_page_count(log_text: str) -> Optional[int]:
    """Read the page count LaTeX reports at the end of its log."""
    match = re.search(r'Output written on \S+ \((\d+) pages?', log_text)
    return int(match.group(1)) if match else None


def find_font_failures(log_text: str, missfont_text: str = '') -> List[str]:
    """Return descriptions of any font failures recorded during the build."""
    problems = []

    for pattern, description in FONT_FAILURE_PATTERNS:
        if re.search(pattern, log_text, re.MULTILINE):
            problems.append(description)

    if missfont_text.strip():
        problems.append('missfont.log is non-empty, so fonts were missing')

    return problems


def compile_pdf() -> Tuple[bool, dict]:
    """Compile LaTeX to PDF using XeLaTeX (run twice for references).

    Returns:
        (success, diagnostics). The diagnostics carry the LaTeX log and
        missfont.log contents, because cleanup_temp_files() deletes both
        before validation runs and they hold the only reliable evidence of
        the font failures we need to catch.
    """
    print(f"Compiling {TEX_FILE.name} to PDF...")

    # Remember the existing PDF so a build that never rewrites it cannot be
    # mistaken for a successful one.
    previous_mtime = PDF_FILE.stat().st_mtime_ns if PDF_FILE.exists() else None

    # Clear the diagnostic files first. LaTeX appends to missfont.log rather
    # than truncating it, so one left behind by an earlier manual run would
    # otherwise fail every subsequent build, however healthy.
    for stale in (LOG_FILE, MISSFONT_FILE):
        stale.unlink(missing_ok=True)

    diagnostics = {'log': '', 'missfont': ''}

    def capture():
        if LOG_FILE.exists():
            diagnostics['log'] = LOG_FILE.read_text(encoding='utf-8', errors='replace')
        if MISSFONT_FILE.exists():
            diagnostics['missfont'] = MISSFONT_FILE.read_text(
                encoding='utf-8', errors='replace'
            )

    # Run xelatex twice for references
    for i in range(2):
        success, stdout, stderr = run_command(
            ['xelatex', '-interaction=nonstopmode', TEX_FILE.name],
            cwd=DOCUMENTS_DIR,
            timeout=120
        )
        capture()

        # A nonzero exit is a hard failure. Previously this fell through
        # whenever a PDF existed on disk, which is exactly how a stale or
        # blank PDF got reported as a successful build.
        if not success:
            print(f"XeLaTeX pass {i+1} failed (nonzero exit status):")
            print(stderr or stdout[-2000:])
            return False, diagnostics

    if not PDF_FILE.exists():
        print("PDF file not created")
        return False, diagnostics

    if previous_mtime is not None and PDF_FILE.stat().st_mtime_ns == previous_mtime:
        print("PDF was not rewritten by this build -- the file on disk is stale")
        return False, diagnostics

    size = PDF_FILE.stat().st_size
    print(f"PDF generated: {PDF_FILE} ({size:,} bytes)")
    return True, diagnostics


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


def validate_output(diagnostics: Optional[dict] = None) -> bool:
    """Validate that PDF and HTML were generated correctly.

    Args:
        diagnostics: Optional dict from compile_pdf() carrying the LaTeX log
            and missfont.log contents. Without it the log-based checks are
            skipped, so callers that care about font failures must pass it.
    """
    print("\nValidating output...")

    diagnostics = diagnostics or {}
    log_text = diagnostics.get('log', '')
    errors = []

    # Check PDF
    if not PDF_FILE.exists():
        errors.append("PDF file not found")
    else:
        size = PDF_FILE.stat().st_size
        if size < MIN_PDF_BYTES:
            errors.append(
                f"PDF is {size:,} bytes, below the {MIN_PDF_BYTES:,} byte floor"
            )

        if not has_valid_pdf_trailer(PDF_FILE):
            errors.append("PDF has no readable trailer, so the file is truncated")

        operators = count_pdf_text_operators(PDF_FILE)
        if operators < MIN_TEXT_OPERATORS:
            errors.append(
                f"PDF draws only {operators} text operators (expected at least "
                f"{MIN_TEXT_OPERATORS}) -- its pages are effectively blank"
            )

        pdf_pages = count_pdf_pages(PDF_FILE)
        if pdf_pages < MIN_PDF_PAGES:
            errors.append(
                f"PDF has {pdf_pages} pages, below the {MIN_PDF_PAGES} page floor"
            )

        # Cross-check the artifact against the log. If the run that wrote
        # this log did not produce this PDF, the file on disk is stale.
        logged_pages = parse_page_count(log_text) if log_text else None
        if logged_pages is not None and logged_pages != pdf_pages:
            errors.append(
                f"LaTeX reported {logged_pages} pages but the PDF has "
                f"{pdf_pages} -- the PDF on disk is not from this build"
            )

    if log_text and parse_page_count(log_text) is None:
        errors.append("LaTeX log has no page count, so the run did not finish")

    for problem in find_font_failures(log_text, diagnostics.get('missfont', '')):
        errors.append(f"Font failure: {problem}")

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

    # Compile PDF. Clean up on every exit path so a failed run never leaves
    # stray .log/.aux/missfont.log files behind to confuse the next build.
    compiled, diagnostics = compile_pdf()
    if not compiled:
        print("Failed to compile PDF")
        cleanup_temp_files()
        return False

    # Compile HTML using custom parser
    if not compile_html():
        print("Failed to generate HTML")
        cleanup_temp_files()
        return False

    # Validate against the diagnostics captured during compilation
    valid = validate_output(diagnostics)

    # Clean up
    cleanup_temp_files()

    if not valid:
        return False

    print("\n" + "=" * 60)
    print("CV build completed successfully!")
    print("=" * 60)
    return True


if __name__ == '__main__':
    success = build_cv()
    sys.exit(0 if success else 1)
