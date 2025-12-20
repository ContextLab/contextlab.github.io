# Contextual Dynamics Lab Website

The official website for the Contextual Dynamics Lab at Dartmouth College, hosted on GitHub Pages.

**Live site:** [https://context-lab.com](https://context-lab.com)

## Site Structure

```
contextlab.github.io/
├── index.html          # Homepage with animated brain
├── research.html       # Research interests and projects
├── people.html         # Current members and alumni (auto-generated)
├── publications.html   # Papers, talks, posters, materials (auto-generated)
├── software.html       # Open-source software projects (auto-generated)
├── contact.html        # Contact form
├── news.html           # Lab news and updates
├── css/
│   └── style.css       # Main stylesheet
├── js/
│   └── main.js         # Interactive components
├── images/
│   ├── brain/          # Animated brain frames
│   ├── people/         # Team member photos
│   ├── publications/   # Publication thumbnails
│   └── software/       # Software project images
├── documents/
│   ├── JRM_CV.tex      # CV LaTeX source (edit this!)
│   ├── JRM_CV.pdf      # Generated PDF (auto-built)
│   └── JRM_CV.html     # Generated HTML (auto-built)
├── data/               # Content source files (edit these!)
│   ├── publications.xlsx
│   ├── people.xlsx
│   └── software.xlsx
├── templates/          # HTML templates for auto-generation
│   ├── publications.html
│   ├── people.html
│   └── software.html
├── scripts/            # Build and validation scripts
│   ├── build.py        # Content page builder
│   ├── build_cv.py     # CV build orchestration
│   ├── extract_cv.py   # LaTeX-to-HTML parser
│   └── ...
└── tests/              # Automated tests
    └── ...
```

## Design & Theming

Site design by [Chameleon Studios](https://www.chamstudios.com/).

### Color Palette

The site uses a green-based color scheme defined in CSS variables:

```css
:root {
    --primary-green: rgb(0, 112, 60);        /* Main brand color */
    --primary-green-light: rgba(0, 112, 60, 0.6);
    --bg-green: rgba(0, 112, 60, 0.2);       /* Page backgrounds */
    --white: #FFFFFF;
    --dark-text: rgba(0, 0, 0, 0.7);
}
```

### Typography

- **Body text:** Nunito Sans (300 weight)
- **Headings:** Nunito Sans (300-700 weight), lowercase with letter-spacing
- Base font size: 14px with 1.7 line-height

### Key Design Elements

1. **Sticky Footer Navigation** - Fixed navigation bar at the bottom of the viewport
2. **Animated Brain** - Homepage features a rotating brain animation (GIF frames)
3. **Info Panel Toggle** - Homepage "i" button reveals lab description with smooth animation
4. **Modal Forms** - Contact and join-us forms appear in centered modals
5. **Publication Cards** - Hover effects reveal additional information

## Pages

### Homepage (index.html)
- Animated brain image that scales with viewport
- "Info" button toggles descriptive panel
- Brain and text resize responsively

### People (people.html)
- Lab director section
- Grid of current members
- "Join Us" modal for prospective members
- Alumni section with past lab members
- Collaborators list

### Publications (publications.html)
- Peer-reviewed articles with thumbnails
- Talks section with video/PDF links
- Course materials
- Conference abstracts and posters

### Contact (contact.html)
- Contact form (Formspree integration)
- Physical address and email

## JavaScript Components

Located in `js/main.js`:

- **initDropdowns()** - Dropdown menu behavior
- **initStickyNav()** - Footer nav visibility on scroll
- **initSlideshow()** - Image carousel with autoplay
- **initModal()** - Modal open/close handling
- **initSmoothScroll()** - Anchor link smooth scrolling
- **initInfoPanel()** - Homepage info toggle with animations
- **initContactForms()** - AJAX form submission
- **initMobileMenu()** - Mobile navigation toggle
- **initCustomValidation()** - Styled form validation messages

## Forms

Contact forms use [Formspree](https://formspree.io/) for processing. Form validation messages are styled to match the site's green theme.

To update the form endpoint:
1. Create a Formspree account
2. Create a new form
3. Replace the `action` URL in the form HTML

## Automated Content Generation

The publications, people, and software pages are **automatically generated** from Excel spreadsheets. This makes it easy to update content without editing HTML directly.

### How It Works

```
data/                          # Source data (edit these!)
├── publications.xlsx          # 104 publications
├── people.xlsx                # 95 people entries
└── software.xlsx              # 20 software items

templates/                     # HTML templates with markers
├── publications.html
├── people.html
└── software.html

scripts/                       # Build scripts
├── build.py                   # Master build script
├── build_publications.py
├── build_people.py
├── build_software.py
├── validate_data.py           # Data validation
├── pre_push_check.py          # Pre-push checks
└── utils.py                   # Shared utilities

# Generated output (don't edit directly!)
├── publications.html
├── people.html
└── software.html
```

### Updating Content

#### Adding a New Publication

1. Open `data/publications.xlsx` in Excel/Google Sheets
2. Go to the appropriate sheet (`papers`, `preprints`, `chapters`, or `other`)
3. Add a new row with:
   - `title` - Publication title
   - `title_url` - Link to paper (DOI, PDF, etc.)
   - `citation` - Full citation text (can include HTML links)
   - `image` - Thumbnail filename (optional, place image in `images/publications/`)
4. Save and push to GitHub (or run build locally)

#### Adding a New Team Member

1. Open `data/people.xlsx` in Excel/Google Sheets
2. Go to the `members` sheet
3. Add a new row with:
   - `name` - Person's name
   - `name_url` - Personal website (optional)
   - `role` - e.g., "grad student", "undergrad", "postdoc"
   - `bio` - Biography text
   - `image` - Photo filename (place photo in `images/people/`)
4. Save and push to GitHub

#### Adding Alumni

1. Open `data/people.xlsx`
2. Go to the appropriate sheet:
   - `alumni_postdocs` - Former postdocs
   - `alumni_grads` - Former graduate students
   - `alumni_managers` - Former lab managers
   - `alumni_undergrads` - Former undergraduates
3. Add a row with:
   - `name` - Person's name
   - `name_url` - Personal website (optional)
   - `current_position` - e.g., "now at Google"
   - `current_position_url` - Link to current employer (optional)

#### Adding Software

1. Open `data/software.xlsx`
2. Go to the appropriate sheet (`python`, `javascript`, or `matlab`)
3. Add a new row with:
   - `name` - Project name
   - `description` - Brief description
   - `links_html` - HTML for links, e.g., `[<a href="https://github.com/..." target="_blank">GitHub</a>]`

### Building Locally

```bash
# Install dependencies
pip install -r requirements-build.txt

# Validate data files
python scripts/validate_data.py

# Build all pages
python scripts/build.py

# Or run the full pre-push check
python scripts/pre_push_check.py
```

### Automatic Builds (GitHub Actions)

When you push changes to `data/`, `templates/`, or `scripts/` on the `main` branch, GitHub Actions automatically:

1. Validates all spreadsheet data
2. Rebuilds the HTML pages
3. Runs the test suite (76 tests)
4. Commits and pushes the regenerated HTML

You can also manually trigger a build from the [Actions tab](https://github.com/ContextLab/contextlab.github.io/actions).

### Spreadsheet Field Reference

#### publications.xlsx

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Publication title |
| `title_url` | No | Link to paper |
| `citation` | Yes | Full citation (HTML allowed) |
| `image` | No | Thumbnail filename |

#### people.xlsx - members sheet

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Person's name |
| `name_url` | No | Personal website |
| `role` | No | Role in lab |
| `bio` | No | Biography text |
| `image` | No | Photo filename |

#### people.xlsx - alumni sheets

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Person's name |
| `name_url` | No | Personal website |
| `current_position` | No | Current role/employer |
| `current_position_url` | No | Link to employer |

#### software.xlsx

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Project name |
| `description` | Yes | Brief description |
| `links_html` | No | HTML links to repo, docs, etc. |

### Tips

- **HTML in cells**: You can use HTML tags in spreadsheet cells (e.g., `<a href="...">`, `<em>`, `<strong>`)
- **Image files**: Place images in the appropriate `images/` subdirectory before referencing them
- **Validation**: Run `python scripts/validate_data.py` to check for missing required fields or broken image references
- **Don't edit generated HTML**: Changes to `publications.html`, `people.html`, and `software.html` in the root directory will be overwritten by the build system

---

## CV Auto-Generation

Jeremy Manning's CV is automatically compiled from LaTeX source into both PDF and HTML formats. The HTML version matches the PDF styling and includes a download button.

### How It Works

```
documents/
├── JRM_CV.tex          # LaTeX source (edit this!)
├── JRM_CV.pdf          # Generated PDF
└── JRM_CV.html         # Generated HTML

scripts/
├── build_cv.py         # Build orchestration
└── extract_cv.py       # Custom LaTeX-to-HTML parser

css/
└── cv.css              # CV-specific stylesheet

data/
└── DartmouthRuzicka-*.ttf  # Dartmouth Ruzicka fonts

.github/workflows/
└── build-cv.yml        # GitHub Actions automation
```

### Updating the CV

1. Edit `documents/JRM_CV.tex` in any LaTeX editor
2. Push to GitHub - the CV will be automatically rebuilt
3. Both PDF and HTML versions are generated and committed

### Building Locally

```bash
# Install dependencies
pip install -r requirements-build.txt

# Build CV (requires XeLaTeX)
cd scripts
python build_cv.py

# Run tests
python -m pytest tests/test_build_cv.py -v
```

### Custom LaTeX Parser

The `extract_cv.py` script provides a custom LaTeX-to-HTML converter that handles:

- **Text formatting**: `\textbf`, `\textit`, `\emph`, `\textsc`, `\ul`
- **Links**: `\href{url}{text}` → `<a href="url">text</a>`
- **Lists**: `etaremune` (reverse-numbered), `itemize`, `enumerate`
- **Multi-column**: `\begin{multicols}{2}` → CSS two-column layout
- **Sections**: `\section*`, `\subsection*` → semantic HTML headings
- **Special characters**: em-dashes, en-dashes, quotes, accented characters
- **Footnotes**: `\blfootnote{}` → section notes displayed inline
- **Block spacing**: `\\[0.1cm]` → visual block separators

### Key Functions in extract_cv.py

| Function | Purpose |
|----------|---------|
| `extract_document_body()` | Extract content between `\begin{document}` and `\end{document}` |
| `balanced_braces_extract()` | Parse nested LaTeX braces correctly |
| `convert_latex_formatting()` | Convert LaTeX commands to HTML |
| `parse_etaremune()` | Parse reverse-numbered publication lists |
| `extract_header_info()` | Extract name and contact information |
| `extract_sections()` | Split document into sections/subsections |
| `render_section_content()` | Convert section content based on type |
| `generate_html()` | Assemble complete HTML document |

### CV Stylesheet (cv.css)

The stylesheet provides:

- **Dartmouth Ruzicka font** via `@font-face` declarations
- **Dartmouth green** color scheme: `rgb(0, 105, 62)`
- **Sticky download bar** at top of page
- **Responsive design** for tablet and mobile
- **Print styles** that match PDF appearance
- **Reverse-numbered lists** using native `<ol reversed>` support

### Automatic Builds (GitHub Actions)

The `build-cv.yml` workflow triggers when you push changes to:
- `documents/JRM_CV.tex`
- `scripts/build_cv.py` or `scripts/extract_cv.py`
- `css/cv.css`
- `.github/workflows/build-cv.yml`

The workflow:
1. Installs TeX Live and Dartmouth Ruzicka fonts
2. Compiles LaTeX to PDF using XeLaTeX
3. Converts LaTeX to HTML using the custom parser
4. Runs 61 automated tests
5. Commits and pushes the generated files

### Testing

The test suite (`tests/test_build_cv.py`) includes 61 tests covering:

- LaTeX formatting conversion
- Balanced brace parsing
- Section extraction
- HTML generation
- PDF compilation
- Content validation
- Link validation
- Edge cases

---

## Adding Content (Legacy/Manual Method)

> **Note:** For publications, people, and software pages, use the spreadsheet method above. The manual method below is for other pages or special cases.

### New Team Member (Manual)

1. Add photo to `images/people/` (recommended: 400x400px)
2. Edit `people.html`, add to appropriate section:

```html
<div class="team-member">
    <img src="images/people/name.jpg" alt="Name">
    <h3>name | role</h3>
    <p>Bio text here.</p>
</div>
```

### New Publication (Manual)

1. Add thumbnail to `images/publications/` (recommended: 500x500px with green border)
2. Edit `publications.html`, add to publications grid:

```html
<div class="publication-card">
    <img src="images/publications/thumbnail.png" alt="Paper title">
    <div class="publication-info">
        <h3>Paper Title</h3>
        <p>Authors (Year). Journal Name.</p>
        <a href="https://doi.org/..." target="_blank">PDF</a>
    </div>
</div>
```

### New Software Project (Manual)

1. Add screenshot to `images/software/`
2. Edit `software.html`, add to software grid

## Adding Hand-Drawn Borders to Images

Poster thumbnails and people photos use hand-drawn green borders for visual consistency. Use the `add_borders.py` script to add these borders to new images.

### Border Script Usage

```bash
# Basic usage
python scripts/add_borders.py <input_dir> <output_dir>

# Example: Process new poster images
python scripts/add_borders.py images/publications/new/ images/publications/

# Example: Process a single image (copy to temp folder first)
mkdir temp_input
cp images/publications/MyPoster.png temp_input/
python scripts/add_borders.py temp_input/ temp_output/
mv temp_output/MyPoster.png images/publications/MyPoster.png
rm -rf temp_input temp_output
```

### How It Works

The script:
1. Loads 10 hand-drawn border designs from `images/templates/WebsiteDoodles_Posters_v1.svg`
2. For each input PNG, selects a random border
3. Resizes the image to fit inside the border frame (poster extends to middle of border lines)
4. Composites the border on top of the image
5. Makes areas outside the border transparent
6. Outputs a 500x500 PNG with ~41px transparent margins

### Adding New Poster Thumbnails

1. Create a thumbnail PNG of the poster (any size, will be resized)
2. Place in a temporary input folder
3. Run the border script
4. Move the output to `images/publications/`
5. Update `data/publications.xlsx` with the image filename

### Adding New People Photos

1. Prepare the photo as a PNG (square crop recommended)
2. Place in a temporary input folder
3. Run the border script
4. Move the output to `images/people/`
5. Update `data/people.xlsx` with the image filename

### Script Options

```bash
python scripts/add_borders.py --help

Options:
  input_dir       Directory containing input PNG files
  output_dir      Directory to save output files
  --border-svg    Path to SVG with border designs (default: images/templates/WebsiteDoodles_Posters_v1.svg)
  --output-size   Output image size in pixels (default: 500)
```

### Requirements

The script requires:
- Python 3
- PIL/Pillow
- NumPy
- `rsvg-convert` (from librsvg, install via `brew install librsvg` on macOS)

## Mobile Responsiveness

The site is fully responsive with breakpoints at:
- **768px** - Tablet layout
- **480px** - Mobile layout

Key mobile adaptations:
- Collapsible navigation menu
- Single-column layouts
- Adjusted font sizes
- Touch-friendly tap targets

## Deployment

The site deploys automatically via GitHub Pages when changes are pushed to the `main` branch.

To test locally, open any HTML file directly in a browser or use a local server:

```bash
python3 -m http.server 8000
# Then visit http://localhost:8000
```

## Browser Support

Tested and supported in:
- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Credits

- **Design:** [Chameleon Studios](https://www.chamstudios.com/)
- **Development:** Contextual Dynamics Lab
- **Hosting:** GitHub Pages
