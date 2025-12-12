# Contextual Dynamics Lab Website

The official website for the Contextual Dynamics Lab at Dartmouth College, hosted on GitHub Pages.

**Live site:** [https://context-lab.com](https://context-lab.com)

## Site Structure

```
contextlab.github.io/
├── index.html          # Homepage with animated brain
├── research.html       # Research interests and projects
├── people.html         # Current members and alumni
├── publications.html   # Papers, talks, posters, and course materials
├── software.html       # Open-source software projects
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
└── documents/
    └── JRM_CV.pdf      # Jeremy Manning's CV
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

## Adding Content

### New Team Member

1. Add photo to `images/people/` (recommended: 400x400px)
2. Edit `people.html`, add to appropriate section:

```html
<div class="team-member">
    <img src="images/people/name.jpg" alt="Name">
    <h3>name | role</h3>
    <p>Bio text here.</p>
</div>
```

### New Publication

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

### New Software Project

1. Add screenshot to `images/software/`
2. Edit `software.html`, add to software grid

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
