"""Tests for CV build system using REAL files - no mocks.

All tests use real file operations, real PDF compilation, and real HTML generation
to verify the actual behavior of the CV build scripts.

IMPORTANT: NO MOCKS OR SIMULATIONS - all tests use real files and real operations.
"""
import pytest
from pathlib import Path
import tempfile
import contextlib
import subprocess
import re

from extract_cv import (
    read_latex_file,
    extract_document_body,
    balanced_braces_extract,
    convert_command,
    convert_href,
    convert_latex_formatting,
    parse_etaremune,
    extract_header_info,
    extract_sections,
    generate_html,
    extract_cv,
)

from build_cv import (
    run_command,
    compile_pdf,
    compile_html,
    cleanup_temp_files,
    validate_output,
    build_cv,
    PDF_FILE,
    TEX_FILE,
    HTML_FILE,
)


class TestLatexConversion:
    """Test LaTeX conversion functions."""

    def test_convert_textbf(self):
        """Test that \\textbf is converted to <strong>."""
        text = r'\textbf{bold text}'
        result = convert_latex_formatting(text)
        assert '<strong>bold text</strong>' in result

    def test_convert_textbf_nested(self):
        """Test nested braces in \\textbf."""
        text = r'\textbf{text with {nested} braces}'
        result = convert_latex_formatting(text)
        assert '<strong>text with {nested} braces</strong>' in result

    def test_convert_href_basic(self):
        """Test basic \\href conversion."""
        text = r'\href{https://example.com}{Link Text}'
        result = convert_latex_formatting(text)
        assert '<a href="https://example.com" target="_blank">Link Text</a>' in result

    def test_convert_href_in_sentence(self):
        """Test \\href within a sentence."""
        text = r'Visit \href{https://example.com}{our site} for more.'
        result = convert_latex_formatting(text)
        assert 'Visit <a href="https://example.com" target="_blank">our site</a> for more.' in result

    def test_convert_multiple_hrefs(self):
        """Test multiple \\href commands."""
        text = r'\href{http://a.com}{Link A} and \href{http://b.com}{Link B}'
        result = convert_latex_formatting(text)
        assert '<a href="http://a.com" target="_blank">Link A</a>' in result
        assert '<a href="http://b.com" target="_blank">Link B</a>' in result

    def test_convert_textit(self):
        """Test \\textit conversion."""
        text = r'\textit{italic text}'
        result = convert_latex_formatting(text)
        assert '<em>italic text</em>' in result

    def test_convert_emph(self):
        """Test \\emph conversion."""
        text = r'\emph{emphasized}'
        result = convert_latex_formatting(text)
        assert '<em>emphasized</em>' in result

    def test_convert_textsc(self):
        """Test \\textsc conversion."""
        text = r'\textsc{Small Caps}'
        result = convert_latex_formatting(text)
        assert '<span class="small-caps">Small Caps</span>' in result

    def test_convert_special_ampersand(self):
        """Test \\& conversion."""
        text = r'Smith \& Jones'
        result = convert_latex_formatting(text)
        assert 'Smith &amp; Jones' in result

    def test_convert_special_underscore(self):
        """Test \\_ conversion."""
        text = r'file\_name'
        result = convert_latex_formatting(text)
        assert 'file_name' in result

    def test_convert_special_percent(self):
        """Test \\% conversion."""
        text = r'50\% off'
        result = convert_latex_formatting(text)
        assert '50% off' in result

    def test_convert_special_dollar(self):
        """Test \\$ conversion."""
        text = r'\$100'
        result = convert_latex_formatting(text)
        assert '$100' in result

    def test_convert_em_dash(self):
        """Test --- to em-dash conversion."""
        text = 'Hello---world'
        result = convert_latex_formatting(text)
        assert 'Hello—world' in result

    def test_convert_en_dash(self):
        """Test -- to en-dash conversion."""
        text = '2020--2025'
        result = convert_latex_formatting(text)
        assert '2020–2025' in result

    def test_convert_quotes(self):
        """Test quote conversion."""
        text = "``Hello'' and `world'"
        result = convert_latex_formatting(text)
        assert '"Hello"' in result
        assert "'world'" in result

    def test_convert_linebreak(self):
        """Test \\\\ to <br> conversion."""
        text = r'Line 1\\Line 2'
        result = convert_latex_formatting(text)
        assert '<br>' in result

    def test_convert_combined_formatting(self):
        """Test multiple formatting commands together."""
        text = r'\textbf{Bold} and \textit{italic} and \href{http://example.com}{link}'
        result = convert_latex_formatting(text)
        assert '<strong>Bold</strong>' in result
        assert '<em>italic</em>' in result
        assert '<a href="http://example.com" target="_blank">link</a>' in result

    def test_balanced_braces_extract(self):
        """Test balanced braces extraction."""
        text = '{simple content}'
        content, end = balanced_braces_extract(text, 0)
        assert content == 'simple content'
        assert end == len(text)

    def test_balanced_braces_nested(self):
        """Test nested braces extraction."""
        text = '{outer {inner} text}'
        content, end = balanced_braces_extract(text, 0)
        assert content == 'outer {inner} text'

    def test_balanced_braces_multiple_levels(self):
        """Test deeply nested braces."""
        text = '{a {b {c} d} e}'
        content, end = balanced_braces_extract(text, 0)
        assert content == 'a {b {c} d} e'

    def test_convert_command_basic(self):
        """Test convert_command function."""
        text = r'\textbf{bold}'
        result = convert_command(text, 'textbf', '<strong>', '</strong>')
        assert result == '<strong>bold</strong>'

    def test_convert_href_function(self):
        """Test convert_href function."""
        text = r'\href{http://example.com}{Link}'
        result = convert_href(text)
        assert '<a href="http://example.com" target="_blank">Link</a>' in result


class TestParseEtaremune:
    """Test etaremune list parsing."""

    def test_parse_simple_list(self):
        """Test parsing a simple etaremune list."""
        content = r'''
\begin{etaremune}
\item First item
\item Second item
\item Third item
\end{etaremune}
'''
        items = parse_etaremune(content)
        assert len(items) == 3
        assert 'First item' in items[0]
        assert 'Second item' in items[1]
        assert 'Third item' in items[2]

    def test_parse_list_with_formatting(self):
        """Test parsing list with LaTeX formatting."""
        content = r'''
\begin{etaremune}
\item \textbf{Bold} text
\item \textit{Italic} text
\item \href{http://example.com}{Link}
\end{etaremune}
'''
        items = parse_etaremune(content)
        assert len(items) == 3
        assert '<strong>Bold</strong>' in items[0]
        assert '<em>Italic</em>' in items[1]
        assert '<a href="http://example.com" target="_blank">Link</a>' in items[2]

    def test_parse_empty_list(self):
        """Test parsing content without etaremune."""
        content = 'No list here'
        items = parse_etaremune(content)
        assert len(items) == 0

    def test_parse_multiline_items(self):
        """Test parsing items that span multiple lines."""
        content = r'''
\begin{etaremune}
\item First line
continues here
\item Second item
\end{etaremune}
'''
        items = parse_etaremune(content)
        assert len(items) == 2
        assert 'First line' in items[0]
        assert 'continues' in items[0]


class TestExtractHeaderInfo:
    """Test header extraction."""

    def test_extract_name(self):
        """Test extracting name from header."""
        body = r'''
{\LARGE Jeremy R. Manning, \textsc{Ph.D.}}\\
Director, Lab\\
Department\\
\section*{Employment}
Content here
'''
        info = extract_header_info(body)
        assert 'name' in info
        assert 'Jeremy R. Manning' in info['name']

    def test_extract_header_lines(self):
        """Test extracting contact info lines."""
        body = r'''
{\LARGE Name}\\[0.25cm]
Department\\
Email: \href{mailto:test@example.com}{test@example.com}\\
\section*{Employment}
'''
        info = extract_header_info(body)
        assert 'header_lines' in info
        assert len(info['header_lines']) > 0
        # header_lines is a list of dicts with 'text' and 'space_after' keys
        texts = [line['text'] if isinstance(line, dict) else line for line in info['header_lines']]
        assert any('Department' in text for text in texts)


class TestExtractSections:
    """Test section extraction."""

    def test_extract_single_section(self):
        """Test extracting a single section."""
        body = r'''
Header content
\section*{Employment}
Employment details here
'''
        sections = extract_sections(body)
        assert len(sections) >= 1
        assert any(s.title == 'Employment' for s in sections)

    def test_extract_multiple_sections(self):
        """Test extracting multiple sections."""
        body = r'''
\section*{Employment}
Job info
\section*{Education}
Degree info
\section*{Publications}
Paper list
'''
        sections = extract_sections(body)
        assert len(sections) >= 3
        titles = [s.title for s in sections]
        assert 'Employment' in titles
        assert 'Education' in titles
        assert 'Publications' in titles

    def test_extract_subsections(self):
        """Test extracting subsections."""
        body = r'''
\section*{Main Section}
Main content
\subsection*{Subsection 1}
Sub content 1
\subsection*{Subsection 2}
Sub content 2
'''
        sections = extract_sections(body)
        main_section = next((s for s in sections if s.title == 'Main Section'), None)
        assert main_section is not None
        assert len(main_section.subsections) >= 2


class TestHTMLGeneration:
    """Test HTML generation."""

    def test_generate_basic_html(self):
        """Test generating basic HTML structure."""
        tex_content = r'''
\documentclass{article}
\begin{document}
{\LARGE Test Name}\\
Test Department\\
\section*{Section}
Content here
\end{document}
'''
        html = generate_html(tex_content)

        # Check structure
        assert '<!DOCTYPE html>' in html
        assert '<html lang="en">' in html
        assert '<head>' in html
        assert '<body>' in html
        assert '</body>' in html
        assert '</html>' in html

    def test_html_has_download_button(self):
        """Test that HTML includes PDF download button."""
        tex_content = r'''
\documentclass{article}
\begin{document}
{\LARGE Test Name}\\
\section*{Section}
Content
\end{document}
'''
        html = generate_html(tex_content)
        assert 'cv-download-bar' in html
        assert 'Download PDF' in html

    def test_html_has_css_link(self):
        """Test that HTML includes CSS link."""
        tex_content = r'''
\documentclass{article}
\begin{document}
{\LARGE Test Name}\\
\section*{Section}
Content
\end{document}
'''
        html = generate_html(tex_content)
        assert 'cv.css' in html

    def test_html_includes_sections(self):
        """Test that HTML includes section content."""
        tex_content = r'''
\documentclass{article}
\begin{document}
{\LARGE Test Name}\\
\section*{Employment}
Professor
\section*{Education}
Ph.D.
\end{document}
'''
        html = generate_html(tex_content)
        assert 'Employment' in html
        assert 'Education' in html
        assert 'Professor' in html

    def test_html_preserves_links(self):
        """Test that links are preserved in HTML."""
        tex_content = r'''
\documentclass{article}
\begin{document}
{\LARGE Test Name}\\
\href{mailto:test@example.com}{test@example.com}\\
\section*{Section}
Visit \href{http://example.com}{our website}
\end{document}
'''
        html = generate_html(tex_content)
        assert 'mailto:test@example.com' in html
        assert 'http://example.com' in html
        assert '<a href=' in html

    def test_extract_cv_creates_file(self):
        """Test that extract_cv creates an HTML file."""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)

            # Create minimal LaTeX file
            tex_file = temp_dir / 'test.tex'
            tex_file.write_text(r'''
\documentclass{article}
\begin{document}
{\LARGE Jeremy R. Manning}\\
\section*{Employment}
Professor
\end{document}
''')

            # Extract to HTML
            html_file = temp_dir / 'test.html'
            success = extract_cv(tex_file, html_file)

            assert success
            assert html_file.exists()

            # Verify content
            content = html_file.read_text()
            assert '<!DOCTYPE html>' in content
            assert 'Jeremy R. Manning' in content
            assert 'Employment' in content


class TestPDFCompilation:
    """Test PDF compilation from LaTeX."""

    def test_xelatex_available(self):
        """Test that xelatex is available on the system."""
        result = subprocess.run(['which', 'xelatex'], capture_output=True)
        if result.returncode != 0:
            pytest.skip("xelatex not available on this system")

    def test_compile_minimal_pdf(self):
        """Test compiling a minimal LaTeX document to PDF."""
        # Check xelatex availability
        result = subprocess.run(['which', 'xelatex'], capture_output=True)
        if result.returncode != 0:
            pytest.skip("xelatex not available")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)

            # Create minimal LaTeX file
            tex_file = temp_dir / 'test.tex'
            tex_file.write_text(r'''
\documentclass{article}
\begin{document}
Hello, World!
\end{document}
''')

            # Compile to PDF
            cmd = ['xelatex', '-interaction=nonstopmode', 'test.tex']
            subprocess.run(cmd, cwd=temp_dir, capture_output=True)

            pdf_file = temp_dir / 'test.pdf'
            assert pdf_file.exists(), "PDF was not created"

            # Check file size
            size = pdf_file.stat().st_size
            assert size > 1000, f"PDF too small: {size} bytes"

    def test_pdf_is_valid(self):
        """Test that generated PDF starts with PDF magic bytes."""
        # Check xelatex availability
        result = subprocess.run(['which', 'xelatex'], capture_output=True)
        if result.returncode != 0:
            pytest.skip("xelatex not available")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)

            tex_file = temp_dir / 'test.tex'
            tex_file.write_text(r'''
\documentclass{article}
\begin{document}
Test PDF content
\end{document}
''')

            cmd = ['xelatex', '-interaction=nonstopmode', 'test.tex']
            subprocess.run(cmd, cwd=temp_dir, capture_output=True)

            pdf_file = temp_dir / 'test.pdf'

            # Read first few bytes
            with open(pdf_file, 'rb') as f:
                header = f.read(5)

            assert header == b'%PDF-', f"Invalid PDF header: {header}"

    def test_pdf_reasonable_size(self):
        """Test that PDF has reasonable file size (> 50KB for real CV)."""
        # This test will use the actual CV file if it exists
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        # Check xelatex availability
        result = subprocess.run(['which', 'xelatex'], capture_output=True)
        if result.returncode != 0:
            pytest.skip("xelatex not available")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)

            # Copy CV to temp dir
            import shutil
            temp_tex = temp_dir / 'JRM_CV.tex'
            shutil.copy(TEX_FILE, temp_tex)

            # Compile (may need fonts, so allow it to fail gracefully)
            cmd = ['xelatex', '-interaction=nonstopmode', 'JRM_CV.tex']
            result = subprocess.run(cmd, cwd=temp_dir, capture_output=True)

            pdf_file = temp_dir / 'JRM_CV.pdf'

            if pdf_file.exists():
                size = pdf_file.stat().st_size
                assert size > 50000, f"PDF too small: {size} bytes (expected > 50KB)"


class TestContentValidation:
    """Test validation of generated content."""

    def test_html_contains_name(self):
        """Test that HTML contains Jeremy R. Manning."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            html_file = temp_dir / 'cv.html'

            success = extract_cv(TEX_FILE, html_file)
            assert success

            content = html_file.read_text()
            assert 'Jeremy R. Manning' in content

    def test_html_contains_required_sections(self):
        """Test that HTML contains required sections."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            html_file = temp_dir / 'cv.html'

            success = extract_cv(TEX_FILE, html_file)
            assert success

            content = html_file.read_text()

            # Required sections
            required_sections = ['Employment', 'Education', 'Publications']
            for section in required_sections:
                assert section in content, f"Missing section: {section}"

    def test_html_contains_email(self):
        """Test that HTML contains contact email."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            html_file = temp_dir / 'cv.html'

            success = extract_cv(TEX_FILE, html_file)
            assert success

            content = html_file.read_text()

            # Should have email link
            assert 'mailto:' in content
            assert 'dartmouth.edu' in content

    def test_html_links_are_valid(self):
        """Test that all links in HTML are well-formed URLs."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            html_file = temp_dir / 'cv.html'

            success = extract_cv(TEX_FILE, html_file)
            assert success

            content = html_file.read_text()

            # Find all href attributes
            href_pattern = r'href="([^"]+)"'
            hrefs = re.findall(href_pattern, content)

            assert len(hrefs) > 0, "No links found in HTML"

            # Check that each href is a valid URL or anchor
            for href in hrefs:
                # Should be http(s), mailto, tel, relative path, or anchor
                assert (href.startswith('http://') or
                        href.startswith('https://') or
                        href.startswith('mailto:') or
                        href.startswith('tel:') or
                        href.startswith('#') or
                        href.endswith('.pdf') or
                        href.endswith('.html') or
                        '/' in href or  # Relative paths
                        '.' in href), f"Invalid href: {href}"

    def test_html_has_proper_structure(self):
        """Test that HTML has proper document structure."""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            tex_file = temp_dir / 'test.tex'
            tex_file.write_text(r'''
\documentclass{article}
\begin{document}
{\LARGE Test Name}\\
\section*{Section}
Content
\end{document}
''')

            html_file = temp_dir / 'test.html'
            success = extract_cv(tex_file, html_file)
            assert success

            content = html_file.read_text()

            # Check structure
            assert content.startswith('<!DOCTYPE html>'), "Missing DOCTYPE"
            assert '<html lang="en">' in content
            assert '<head>' in content
            assert '<meta charset="UTF-8">' in content
            assert '<title>' in content
            assert '</title>' in content
            assert '</head>' in content
            assert '<body>' in content
            assert '</body>' in content
            assert '</html>' in content


class TestBuildCVIntegration:
    """Integration tests for the full build process."""

    def test_run_command(self):
        """Test run_command function."""
        success, stdout, stderr = run_command(['echo', 'test'])
        assert success
        assert 'test' in stdout

    def test_run_command_timeout(self):
        """Test run_command with timeout."""
        success, stdout, stderr = run_command(['sleep', '10'], timeout=1)
        assert not success
        assert 'timeout' in stderr.lower() or 'timed out' in stderr.lower()

    def test_cleanup_temp_files(self):
        """Test cleanup of temporary LaTeX files."""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)

            # Create fake temp files
            extensions = ['.aux', '.log', '.out', '.synctex.gz']
            for ext in extensions:
                (temp_dir / f'test{ext}').touch()

            # Monkey-patch DOCUMENTS_DIR
            import build_cv
            old_dir = build_cv.DOCUMENTS_DIR
            build_cv.DOCUMENTS_DIR = temp_dir

            try:
                cleanup_temp_files()

                # Check that files were removed
                for ext in extensions:
                    assert not (temp_dir / f'test{ext}').exists()
            finally:
                build_cv.DOCUMENTS_DIR = old_dir

    def test_full_cv_build_if_files_exist(self):
        """Test full CV build process if source files exist."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        # Check xelatex availability
        result = subprocess.run(['which', 'xelatex'], capture_output=True)
        if result.returncode != 0:
            pytest.skip("xelatex not available")

        # Save original files if they exist
        import shutil
        backup_pdf = None
        backup_html = None

        if PDF_FILE.exists():
            backup_pdf = PDF_FILE.with_suffix('.pdf.backup')
            shutil.copy(PDF_FILE, backup_pdf)

        if HTML_FILE.exists():
            backup_html = HTML_FILE.with_suffix('.html.backup')
            shutil.copy(HTML_FILE, backup_html)

        try:
            # Run build
            success = build_cv()

            if success:
                # Verify outputs
                assert PDF_FILE.exists(), "PDF not created"
                assert HTML_FILE.exists(), "HTML not created"

                # Check PDF is valid
                with open(PDF_FILE, 'rb') as f:
                    header = f.read(5)
                assert header == b'%PDF-', "Invalid PDF"

                # Check HTML has content
                content = HTML_FILE.read_text()
                assert len(content) > 10000, "HTML too small"
                assert 'Jeremy R. Manning' in content

        finally:
            # Restore backups
            if backup_pdf and backup_pdf.exists():
                shutil.move(backup_pdf, PDF_FILE)
            if backup_html and backup_html.exists():
                shutil.move(backup_html, HTML_FILE)


class TestRealCVContent:
    """Tests using the actual CV file."""

    def test_actual_cv_has_employment(self):
        """Test that actual CV has Employment section."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        content = read_latex_file(TEX_FILE)
        assert r'\section*{Employment}' in content or r'\section{Employment}' in content

    def test_actual_cv_has_education(self):
        """Test that actual CV has Education section."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        content = read_latex_file(TEX_FILE)
        assert r'\section*{Education}' in content or r'\section{Education}' in content

    def test_actual_cv_has_publications(self):
        """Test that actual CV has Publications section."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        content = read_latex_file(TEX_FILE)
        assert r'\section*{Publications}' in content or r'\section{Publications}' in content

    def test_extract_cv_from_actual_file(self):
        """Test extracting HTML from the actual CV LaTeX file."""
        if not TEX_FILE.exists():
            pytest.skip("JRM_CV.tex not found")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            html_file = temp_dir / 'JRM_CV.html'

            success = extract_cv(TEX_FILE, html_file)
            assert success, "Failed to extract CV"
            assert html_file.exists(), "HTML file not created"

            content = html_file.read_text()

            # Should be substantial (at least 10KB)
            assert len(content) > 10000, f"HTML too small: {len(content)} bytes"

            # Should have structure
            assert '<!DOCTYPE html>' in content
            assert '<html' in content
            assert '</html>' in content

            # Should have key content
            assert 'Jeremy R. Manning' in content
            assert 'Employment' in content
            assert 'Education' in content
            assert 'Publications' in content

            # Should have download button
            assert 'cv-download-bar' in content
            assert 'Download PDF' in content


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_cv_nonexistent_file(self):
        """Test extracting from nonexistent file."""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            nonexistent = temp_dir / 'nonexistent.tex'
            output = temp_dir / 'output.html'

            # Should handle gracefully
            success = extract_cv(nonexistent, output)
            assert not success

    def test_balanced_braces_no_closing(self):
        """Test balanced_braces_extract with no closing brace."""
        text = '{unclosed'
        content, end = balanced_braces_extract(text, 0)
        assert content is None
        assert end == -1

    def test_balanced_braces_not_starting_with_brace(self):
        """Test balanced_braces_extract when not starting with brace."""
        text = 'no brace here'
        content, end = balanced_braces_extract(text, 0)
        assert content is None
        assert end == -1

    def test_convert_latex_empty_string(self):
        """Test converting empty string."""
        result = convert_latex_formatting('')
        assert result == ''

    def test_parse_etaremune_malformed(self):
        """Test parsing malformed etaremune."""
        content = r'\begin{etaremune}'  # No end tag
        items = parse_etaremune(content)
        assert len(items) == 0

    def test_extract_document_body_no_document(self):
        """Test extracting body when no document environment."""
        latex = 'Just some text'
        body = extract_document_body(latex)
        assert body == latex  # Returns original if no document env found

    def test_generate_html_minimal_document(self):
        """Test generating HTML from minimal document."""
        tex = r'''
\documentclass{article}
\begin{document}
{\LARGE Test Name}\\
\section*{Test Section}
Minimal content here
\end{document}
'''
        html = generate_html(tex)
        assert '<!DOCTYPE html>' in html
        # Content appears in sections, check for section title instead
        assert 'Test Section' in html or 'Test Name' in html


NULLFONT_TEX = r"""\documentclass{article}
\font\monaco=Monaco at 10pt
\begin{document}
\monaco
\newcommand{\pg}{Jeremy R. Manning --- Curriculum Vitae. Employment. Education.
Publications.\par\vfill\eject}
\pg\pg\pg\pg\pg\pg\pg\pg\pg\pg
\end{document}
"""


@pytest.fixture(scope="module")
def blank_pdf_build(tmp_path_factory):
    """Build a REAL blank PDF via the nullfont failure mode.

    Requesting a system font (Monaco) under pdflatex sends LaTeX down the
    legacy TFM lookup path. That lookup fails, LaTeX substitutes `nullfont`,
    and the run emits a structurally valid PDF with the right page count and
    zero glyphs. This is the exact failure that produced a 10-page blank CV.
    """
    if subprocess.run(['which', 'pdflatex'], capture_output=True).returncode != 0:
        pytest.skip("pdflatex not available")

    work = tmp_path_factory.mktemp("nullfont")
    (work / 'repro.tex').write_text(NULLFONT_TEX, encoding='utf-8')
    subprocess.run(
        ['pdflatex', '-interaction=nonstopmode', 'repro.tex'],
        cwd=work, capture_output=True, timeout=120
    )

    pdf = work / 'repro.pdf'
    log = work / 'repro.log'
    if not pdf.exists() or not log.exists():
        pytest.skip("could not reproduce the nullfont failure on this machine")

    missfont = work / 'missfont.log'
    return {
        'pdf': pdf,
        'log': log.read_text(encoding='utf-8', errors='replace'),
        'missfont': missfont.read_text(encoding='utf-8', errors='replace')
        if missfont.exists() else '',
    }


@pytest.fixture(scope="module")
def healthy_log(tmp_path_factory):
    """Compile the real CV with xelatex and return its log."""
    if not TEX_FILE.exists():
        pytest.skip("JRM_CV.tex not found")
    if subprocess.run(['which', 'xelatex'], capture_output=True).returncode != 0:
        pytest.skip("xelatex not available")

    work = tmp_path_factory.mktemp("healthy")
    (work / 'JRM_CV.tex').write_text(TEX_FILE.read_text(encoding='utf-8'), encoding='utf-8')
    subprocess.run(
        ['xelatex', '-interaction=nonstopmode', 'JRM_CV.tex'],
        cwd=work, capture_output=True, timeout=120
    )

    log = work / 'JRM_CV.log'
    pdf = work / 'JRM_CV.pdf'
    if not log.exists() or not pdf.exists():
        pytest.skip("CV did not compile in the temp directory")
    return {'log': log.read_text(encoding='utf-8', errors='replace'), 'pdf': pdf}


class TestPdfContentGuardrails:
    """Guardrails from issue #15: a build that emits no glyphs must not pass."""

    def test_real_cv_draws_plenty_of_text(self, healthy_log):
        import build_cv
        operators = build_cv.count_pdf_text_operators(healthy_log['pdf'])
        assert operators >= build_cv.MIN_TEXT_OPERATORS

    def test_blank_pdf_draws_almost_no_text(self, blank_pdf_build):
        import build_cv
        operators = build_cv.count_pdf_text_operators(blank_pdf_build['pdf'])
        assert operators < build_cv.MIN_TEXT_OPERATORS

    def test_page_count_parsed_from_real_log(self, healthy_log):
        import build_cv
        pages = build_cv.parse_page_count(healthy_log['log'])
        assert pages is not None and pages >= build_cv.MIN_PDF_PAGES

    def test_page_count_alone_would_not_catch_the_blank_pdf(self, blank_pdf_build):
        """The blank PDF has a plausible page count, which is why it slipped through."""
        import build_cv
        pages = build_cv.parse_page_count(blank_pdf_build['log'])
        assert pages is not None and pages > 1

    def test_healthy_log_reports_no_font_failures(self, healthy_log):
        """A good build must stay clean, despite benign 'not found' log lines."""
        import build_cv
        assert build_cv.find_font_failures(healthy_log['log'], '') == []

    def test_healthy_log_contains_benign_not_found(self, healthy_log):
        """Documents why the font check can't just grep for 'not found'."""
        assert 'not found' in healthy_log['log']

    def test_nullfont_log_reports_font_failures(self, blank_pdf_build):
        import build_cv
        problems = build_cv.find_font_failures(
            blank_pdf_build['log'], blank_pdf_build['missfont']
        )
        assert problems, "nullfont substitution was not detected"
        assert any('nullfont' in p for p in problems)

    def test_validate_output_rejects_blank_pdf(self, blank_pdf_build):
        import build_cv
        original = build_cv.PDF_FILE
        try:
            build_cv.PDF_FILE = blank_pdf_build['pdf']
            assert build_cv.validate_output({
                'log': blank_pdf_build['log'],
                'missfont': blank_pdf_build['missfont'],
            }) is False
        finally:
            build_cv.PDF_FILE = original

    def test_validate_output_accepts_the_real_build(self, healthy_log):
        import build_cv
        if not HTML_FILE.exists():
            pytest.skip("JRM_CV.html not found")
        original = build_cv.PDF_FILE
        try:
            build_cv.PDF_FILE = healthy_log['pdf']
            assert build_cv.validate_output({'log': healthy_log['log'], 'missfont': ''}) is True
        finally:
            build_cv.PDF_FILE = original

    def test_missfont_file_alone_is_a_failure(self):
        import build_cv
        problems = build_cv.find_font_failures('', 'Monaco\n')
        assert any('missfont' in p for p in problems)

    def test_empty_missfont_is_not_a_failure(self):
        import build_cv
        assert build_cv.find_font_failures('', '   \n') == []


@contextlib.contextmanager
def documents_dir_at(path):
    """Point build_cv's module-level paths at a scratch directory."""
    import build_cv

    saved = {
        name: getattr(build_cv, name)
        for name in ('DOCUMENTS_DIR', 'TEX_FILE', 'PDF_FILE', 'HTML_FILE',
                     'LOG_FILE', 'MISSFONT_FILE')
    }
    build_cv.DOCUMENTS_DIR = path
    build_cv.TEX_FILE = path / 'JRM_CV.tex'
    build_cv.PDF_FILE = path / 'JRM_CV.pdf'
    build_cv.HTML_FILE = path / 'JRM_CV.html'
    build_cv.LOG_FILE = path / 'JRM_CV.log'
    build_cv.MISSFONT_FILE = path / 'missfont.log'
    try:
        yield build_cv
    finally:
        for name, value in saved.items():
            setattr(build_cv, name, value)


@contextlib.contextmanager
def threshold(name, value):
    """Temporarily move one guardrail threshold."""
    import build_cv

    saved = getattr(build_cv, name)
    setattr(build_cv, name, value)
    try:
        yield build_cv
    finally:
        setattr(build_cv, name, saved)


MINIMAL_TEX = r"""\documentclass{article}
\begin{document}
Hello.
\end{document}
"""

BROKEN_TEX = r"""\documentclass{article}
\begin{document}
\thisCommandDoesNotExist
\end{document}
"""


def _require_xelatex():
    if subprocess.run(['which', 'xelatex'], capture_output=True).returncode != 0:
        pytest.skip("xelatex not available")


class TestCompileFailurePropagation:
    """A failed compile must never be reported as a successful build."""

    def test_nonzero_exit_fails_even_when_a_pdf_exists(self, tmp_path):
        """The regression that let a stale PDF pass as a fresh build."""
        _require_xelatex()
        (tmp_path / 'JRM_CV.tex').write_text(BROKEN_TEX, encoding='utf-8')

        stale = tmp_path / 'JRM_CV.pdf'
        stale.write_bytes(b'%PDF-1.5\nleftover from an earlier build\n%%EOF\n')

        with documents_dir_at(tmp_path) as build_cv:
            compiled, diagnostics = build_cv.compile_pdf()

        assert compiled is False, "nonzero xelatex exit was treated as success"
        assert stale.exists(), "the stale PDF should be left alone, not deleted"

    def test_build_cv_fails_when_compilation_fails(self, tmp_path):
        _require_xelatex()
        (tmp_path / 'JRM_CV.tex').write_text(BROKEN_TEX, encoding='utf-8')
        (tmp_path / 'JRM_CV.pdf').write_bytes(b'%PDF-1.5\nstale\n%%EOF\n')

        with documents_dir_at(tmp_path) as build_cv:
            assert build_cv.build_cv() is False

    def test_unrewritten_pdf_is_rejected_as_stale(self, tmp_path):
        """A compile that succeeds without touching the PDF must not pass."""
        _require_xelatex()

        # Compile a document whose output is NOT the PDF build_cv watches,
        # so the file on disk survives the run untouched.
        (tmp_path / 'other.tex').write_text(MINIMAL_TEX, encoding='utf-8')
        watched = tmp_path / 'JRM_CV.pdf'
        watched.write_bytes(b'%PDF-1.5\nstale but present\n%%EOF\n')
        before = watched.stat().st_mtime_ns

        with documents_dir_at(tmp_path) as build_cv:
            build_cv.TEX_FILE = tmp_path / 'other.tex'
            compiled, _ = build_cv.compile_pdf()

        assert watched.stat().st_mtime_ns == before, "test setup: PDF was rewritten"
        assert compiled is False, "an untouched PDF was accepted as a fresh build"

    def test_stale_missfont_does_not_fail_a_good_build(self, tmp_path):
        """A leftover missfont.log must not condemn an otherwise clean build."""
        _require_xelatex()
        (tmp_path / 'JRM_CV.tex').write_text(MINIMAL_TEX, encoding='utf-8')
        (tmp_path / 'missfont.log').write_text('Monaco\n', encoding='utf-8')

        with documents_dir_at(tmp_path) as build_cv:
            compiled, diagnostics = build_cv.compile_pdf()

        assert compiled is True
        assert diagnostics['missfont'] == '', "stale missfont.log leaked into diagnostics"
        assert build_cv.find_font_failures(diagnostics['log'], diagnostics['missfont']) == []


class TestValidationThresholdsAreEnforced:
    """Each floor must actually be consulted, not merely defined."""

    def test_size_floor_is_consulted(self, healthy_log):
        import build_cv

        original = build_cv.PDF_FILE
        real_size = healthy_log['pdf'].stat().st_size
        try:
            build_cv.PDF_FILE = healthy_log['pdf']
            with threshold('MIN_PDF_BYTES', real_size + 1):
                assert build_cv.validate_output({'log': healthy_log['log']}) is False
        finally:
            build_cv.PDF_FILE = original

    def test_page_floor_is_consulted(self, healthy_log):
        import build_cv

        original = build_cv.PDF_FILE
        real_pages = build_cv.count_pdf_pages(healthy_log['pdf'])
        try:
            build_cv.PDF_FILE = healthy_log['pdf']
            with threshold('MIN_PDF_PAGES', real_pages + 1):
                assert build_cv.validate_output({'log': healthy_log['log']}) is False
        finally:
            build_cv.PDF_FILE = original

    def test_operator_floor_is_consulted(self, healthy_log):
        import build_cv

        original = build_cv.PDF_FILE
        real_ops = build_cv.count_pdf_text_operators(healthy_log['pdf'])
        try:
            build_cv.PDF_FILE = healthy_log['pdf']
            with threshold('MIN_TEXT_OPERATORS', real_ops + 1):
                assert build_cv.validate_output({'log': healthy_log['log']}) is False
        finally:
            build_cv.PDF_FILE = original


class TestTruncatedPdf:
    """A cut-off PDF keeps its content streams, so text alone can't catch it."""

    def test_truncated_pdf_has_no_trailer(self, healthy_log, tmp_path):
        import build_cv

        truncated = tmp_path / 'truncated.pdf'
        truncated.write_bytes(healthy_log['pdf'].read_bytes()[:60_000])

        assert build_cv.has_valid_pdf_trailer(healthy_log['pdf']) is True
        assert build_cv.has_valid_pdf_trailer(truncated) is False

    def test_truncated_pdf_keeps_its_text_operators(self, healthy_log, tmp_path):
        """Documents why the trailer and page checks are needed at all."""
        import build_cv

        truncated = tmp_path / 'truncated.pdf'
        truncated.write_bytes(healthy_log['pdf'].read_bytes()[:60_000])

        assert build_cv.count_pdf_text_operators(truncated) >= build_cv.MIN_TEXT_OPERATORS

    def test_validate_output_rejects_truncated_pdf(self, healthy_log, tmp_path):
        import build_cv

        truncated = tmp_path / 'truncated.pdf'
        truncated.write_bytes(healthy_log['pdf'].read_bytes()[:60_000])

        original = build_cv.PDF_FILE
        try:
            build_cv.PDF_FILE = truncated
            assert build_cv.validate_output({'log': healthy_log['log']}) is False
        finally:
            build_cv.PDF_FILE = original


class TestPdfLogCrossCheck:
    """The PDF and the log must describe the same document."""

    def test_page_count_read_from_pdf_matches_the_log(self, healthy_log):
        import build_cv

        assert build_cv.count_pdf_pages(healthy_log['pdf']) == build_cv.parse_page_count(
            healthy_log['log']
        )

    def test_disagreeing_log_and_pdf_are_rejected(self, healthy_log):
        """A log from a different run than the PDF on disk means it's stale."""
        import build_cv

        mismatched = healthy_log['log'].replace(
            'Output written on JRM_CV.pdf (14 pages',
            'Output written on JRM_CV.pdf (99 pages',
        )
        if mismatched == healthy_log['log']:
            pytest.skip("log format changed; page-count line not found")

        original = build_cv.PDF_FILE
        try:
            build_cv.PDF_FILE = healthy_log['pdf']
            assert build_cv.validate_output({'log': mismatched}) is False
        finally:
            build_cv.PDF_FILE = original


# Errors on the second page, so xelatex exits nonzero but still writes a PDF.
# That combination isolates the exit-status check from the stale-PDF check.
PARTIAL_TEX = r"""\documentclass{article}
\begin{document}
Page one has real content here.
\clearpage
\thisCommandDoesNotExist
Second page.
\end{document}
"""


class TestGuardsInIsolation:
    """Each guard must work on its own, not only via defense in depth.

    Every check below is verified with the OTHER checks neutralized, so that
    a regression in one is not masked by another catching the same artifact.
    """

    def test_nonzero_exit_fails_even_when_the_pdf_is_rewritten(self, tmp_path):
        """Isolates the exit-status check from the stale-PDF check."""
        _require_xelatex()
        (tmp_path / 'JRM_CV.tex').write_text(PARTIAL_TEX, encoding='utf-8')

        with documents_dir_at(tmp_path) as build_cv:
            compiled, _ = build_cv.compile_pdf()
            rewritten = build_cv.PDF_FILE.exists()

        assert rewritten, "test setup: expected a partial PDF to be written"
        assert compiled is False, "nonzero exit passed because a PDF was produced"

    def test_trailer_check_alone_rejects_truncation(self, healthy_log, tmp_path):
        """Isolates the trailer check by zeroing every other floor."""
        import build_cv

        truncated = tmp_path / 'truncated.pdf'
        truncated.write_bytes(healthy_log['pdf'].read_bytes()[:60_000])

        original = build_cv.PDF_FILE
        try:
            build_cv.PDF_FILE = truncated
            with threshold('MIN_PDF_BYTES', 0), threshold('MIN_PDF_PAGES', 0), \
                    threshold('MIN_TEXT_OPERATORS', 0):
                assert build_cv.validate_output({}) is False
        finally:
            build_cv.PDF_FILE = original

    def test_font_check_alone_rejects_the_blank_pdf(self, blank_pdf_build):
        """Isolates the log-based font check by zeroing every floor."""
        import build_cv

        original = build_cv.PDF_FILE
        try:
            build_cv.PDF_FILE = blank_pdf_build['pdf']
            with threshold('MIN_PDF_BYTES', 0), threshold('MIN_PDF_PAGES', 0), \
                    threshold('MIN_TEXT_OPERATORS', 0):
                assert build_cv.validate_output({
                    'log': blank_pdf_build['log'],
                    'missfont': blank_pdf_build['missfont'],
                }) is False
        finally:
            build_cv.PDF_FILE = original

    def test_operator_floor_alone_rejects_the_blank_pdf(self, blank_pdf_build):
        """Isolates the text-operator floor: no log, no size or page floor."""
        import build_cv

        original = build_cv.PDF_FILE
        try:
            build_cv.PDF_FILE = blank_pdf_build['pdf']
            with threshold('MIN_PDF_BYTES', 0), threshold('MIN_PDF_PAGES', 0):
                assert build_cv.validate_output({}) is False
        finally:
            build_cv.PDF_FILE = original


class TestThresholdValues:
    """Pin the floors so they cannot be quietly weakened back to uselessness."""

    def test_page_floor_is_above_the_degraded_page_count(self):
        """The nullfont CV was 10 pages, so a floor at or below 10 is inert."""
        import build_cv
        assert build_cv.MIN_PDF_PAGES > 10

    def test_size_floor_is_above_a_severely_short_cv(self):
        """Embedded fonts mean even a 4-page CV weighs ~75,000 bytes."""
        import build_cv
        assert build_cv.MIN_PDF_BYTES > 75_000

    def test_operator_floor_is_well_above_a_blank_document(self):
        import build_cv
        assert build_cv.MIN_TEXT_OPERATORS >= 500

    def test_real_cv_clears_every_floor(self, healthy_log):
        """The thresholds must not be so tight that a good build fails."""
        import build_cv
        assert healthy_log['pdf'].stat().st_size >= build_cv.MIN_PDF_BYTES
        assert build_cv.count_pdf_pages(healthy_log['pdf']) >= build_cv.MIN_PDF_PAGES
        assert (build_cv.count_pdf_text_operators(healthy_log['pdf'])
                >= build_cv.MIN_TEXT_OPERATORS)
