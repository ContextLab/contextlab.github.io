// Context Lab Website - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initDropdowns();
    initStickyNav();
    initSlideshow();
    initModal();
    initSmoothScroll();
    initInfoPanel();
    initContactForms();
    initMobileMenu();
    initCustomValidation();
});

// Dropdown Menu
function initDropdowns() {
    const dropdowns = document.querySelectorAll('.dropdown');

    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');

        if (toggle) {
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                dropdown.classList.toggle('active');
            });
        }

        // Close on click outside
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.remove('active');
            }
        });
    });
}

// Sticky Footer Navigation
function initStickyNav() {
    const footerNav = document.querySelector('.footer-nav');
    if (!footerNav) return;

    let lastScroll = 0;
    const threshold = 200;

    window.addEventListener('scroll', function() {
        const currentScroll = window.pageYOffset;

        if (currentScroll > threshold) {
            footerNav.classList.add('visible');
        } else {
            footerNav.classList.remove('visible');
        }

        lastScroll = currentScroll;
    });
}

// Slideshow
function initSlideshow() {
    const container = document.querySelector('.slideshow-container');
    if (!container) return;

    const slides = container.querySelectorAll('.slide');
    const dots = container.parentElement.querySelectorAll('.dot');
    const prevBtn = container.querySelector('.slideshow-nav.prev');
    const nextBtn = container.querySelector('.slideshow-nav.next');

    let currentSlide = 0;
    let autoPlayInterval;

    function showSlide(index) {
        // Handle wrap-around
        if (index >= slides.length) index = 0;
        if (index < 0) index = slides.length - 1;

        currentSlide = index;

        // Update slides
        slides.forEach((slide, i) => {
            slide.classList.remove('active');
            if (i === index) slide.classList.add('active');
        });

        // Update dots
        dots.forEach((dot, i) => {
            dot.classList.remove('active');
            if (i === index) dot.classList.add('active');
        });
    }

    function nextSlide() {
        showSlide(currentSlide + 1);
    }

    function prevSlide() {
        showSlide(currentSlide - 1);
    }

    function startAutoPlay() {
        autoPlayInterval = setInterval(nextSlide, 5000);
    }

    function stopAutoPlay() {
        clearInterval(autoPlayInterval);
    }

    // Event listeners
    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
            stopAutoPlay();
            prevSlide();
            startAutoPlay();
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            stopAutoPlay();
            nextSlide();
            startAutoPlay();
        });
    }

    dots.forEach((dot, index) => {
        dot.addEventListener('click', function() {
            stopAutoPlay();
            showSlide(index);
            startAutoPlay();
        });
    });

    // Initialize
    showSlide(0);
    startAutoPlay();

    // Pause on hover
    container.addEventListener('mouseenter', stopAutoPlay);
    container.addEventListener('mouseleave', startAutoPlay);
}

// Modal
function initModal() {
    const modalTriggers = document.querySelectorAll('[data-modal]');

    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            const modalId = this.getAttribute('data-modal');
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
        });
    });

    // Close buttons
    document.querySelectorAll('.modal-close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    // Close on overlay click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            });
        }
    });
}

// Smooth Scroll for anchor links
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;

            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Formspree AJAX submission handler
function initContactForms() {
    const forms = document.querySelectorAll('.contact-form');

    forms.forEach(form => {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.textContent = 'Sending...';
            submitBtn.disabled = true;

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                if (response.ok) {
                    // Show success message
                    form.innerHTML = '<div class="form-success"><h3>Thank you!</h3><p>Your message has been sent. We\'ll get back to you soon.</p></div>';
                } else {
                    throw new Error('Form submission failed');
                }
            } catch (error) {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
                alert('There was a problem sending your message. Please try again or email us directly at contextualdynamics@gmail.com');
            }
        });
    });
}

// Info Panel Toggle (homepage only)
function initInfoPanel() {
    const infoButton = document.querySelector('.info-button');

    if (!infoButton) return;

    infoButton.addEventListener('click', function() {
        const isActive = document.body.classList.contains('info-active');

        // Add transitioning class to enable animation (50% faster: 0.27s)
        document.body.classList.add('info-transitioning');

        if (isActive) {
            // Hide info panel (gallery view)
            document.body.classList.remove('info-active');
            infoButton.classList.remove('active');
        } else {
            // Show info panel (gallery view)
            document.body.classList.add('info-active');
            infoButton.classList.add('active');
        }

        // Remove transitioning class after animation completes
        setTimeout(function() {
            document.body.classList.remove('info-transitioning');
        }, 270); // Match the 0.27s transition duration
    });
}

// Mobile Menu Toggle
function initMobileMenu() {
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const footerNav = document.querySelector('.footer-nav');

    if (!menuToggle || !footerNav) return;

    menuToggle.addEventListener('click', function() {
        footerNav.classList.toggle('menu-open');
    });

    // Close menu when clicking a link
    footerNav.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', function() {
            footerNav.classList.remove('menu-open');
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', function(e) {
        if (!footerNav.contains(e.target)) {
            footerNav.classList.remove('menu-open');
        }
    });
}

// Custom Form Validation Messages
function initCustomValidation() {
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, select, textarea');

        inputs.forEach(input => {
            // Custom validation message on invalid
            input.addEventListener('invalid', function(e) {
                e.preventDefault(); // Prevent default browser tooltip
                showValidationMessage(input);
            });

            // Remove validation message on input
            input.addEventListener('input', function() {
                removeValidationMessage(input);
            });

            // Remove validation message on focus out
            input.addEventListener('blur', function() {
                removeValidationMessage(input);
            });
        });
    });
}

function showValidationMessage(input) {
    // Remove any existing message
    removeValidationMessage(input);

    // Create validation message element
    const message = document.createElement('div');
    message.className = 'validation-message';
    message.textContent = input.validationMessage || 'Please fill out this field';

    // Position it relative to the input's parent (.form-group)
    const formGroup = input.closest('.form-group');
    if (formGroup) {
        formGroup.appendChild(message);
    }

    // Auto-remove after 3 seconds
    setTimeout(() => {
        removeValidationMessage(input);
    }, 3000);
}

function removeValidationMessage(input) {
    const formGroup = input.closest('.form-group');
    if (formGroup) {
        const existingMessage = formGroup.querySelector('.validation-message');
        if (existingMessage) {
            existingMessage.remove();
        }
    }
}
