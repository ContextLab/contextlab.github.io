// Bluesky Feed Integration for Context Lab Website
// Fetches and displays recent posts from @contextlab.bsky.social

(function() {
    'use strict';

    const BLUESKY_HANDLE = 'contextlab.bsky.social';
    const API_URL = `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=${BLUESKY_HANDLE}&limit=10`;
    const FEED_CONTAINER_ID = 'bluesky-feed';

    /**
     * Format a date string for display
     * @param {string} dateString - ISO date string from Bluesky API
     * @returns {string} Formatted date like "Dec 15, 2025"
     */
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    }

    /**
     * Create a text node or link from text, handling URLs safely
     * @param {string} text - Text that may contain URLs
     * @param {Element} container - Container element to append to
     */
    function appendTextWithLinks(text, container) {
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        const parts = text.split(urlRegex);

        parts.forEach(part => {
            if (urlRegex.test(part)) {
                // Reset regex lastIndex after test
                urlRegex.lastIndex = 0;
                const link = document.createElement('a');
                link.href = part;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = part;
                container.appendChild(link);
            } else if (part) {
                container.appendChild(document.createTextNode(part));
            }
        });
    }

    /**
     * Create an SVG icon element
     * @param {string} pathD - SVG path d attribute
     * @returns {Element} SVG element
     */
    function createSvgIcon(pathD) {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('width', '16');
        svg.setAttribute('height', '16');

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('fill', 'currentColor');
        path.setAttribute('d', pathD);
        svg.appendChild(path);

        return svg;
    }

    /**
     * Create a stat link element (likes, reposts, replies)
     * @param {string} url - Link URL
     * @param {string} iconPath - SVG path for icon
     * @param {number} count - Stat count
     * @returns {Element} Anchor element
     */
    function createStatLink(url, iconPath, count) {
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'bluesky-stat';
        link.appendChild(createSvgIcon(iconPath));
        link.appendChild(document.createTextNode(' ' + count));
        return link;
    }

    /**
     * Render a single Bluesky post using safe DOM methods
     * @param {Object} feedItem - Feed item from Bluesky API
     * @returns {Element} Article element for the post
     */
    function renderBlueskyPost(feedItem) {
        const post = feedItem.post;
        const record = post.record;
        const author = post.author;

        // Build post URL
        const postUri = post.uri;
        const postId = postUri.split('/').pop();
        const postUrl = `https://bsky.app/profile/${encodeURIComponent(author.handle)}/post/${encodeURIComponent(postId)}`;
        const profileUrl = `https://bsky.app/profile/${encodeURIComponent(author.handle)}`;

        // Create article element
        const article = document.createElement('article');
        article.className = 'bluesky-post';

        // Header section
        const header = document.createElement('div');
        header.className = 'bluesky-post-header';

        // Author link
        const authorLink = document.createElement('a');
        authorLink.href = profileUrl;
        authorLink.target = '_blank';
        authorLink.rel = 'noopener noreferrer';
        authorLink.className = 'bluesky-author';

        if (author.avatar) {
            const avatar = document.createElement('img');
            avatar.src = author.avatar;
            avatar.alt = author.displayName || author.handle;
            avatar.className = 'bluesky-avatar';
            authorLink.appendChild(avatar);
        }

        const authorInfo = document.createElement('div');
        authorInfo.className = 'bluesky-author-info';

        const displayName = document.createElement('span');
        displayName.className = 'bluesky-display-name';
        displayName.textContent = author.displayName || author.handle;
        authorInfo.appendChild(displayName);

        const handle = document.createElement('span');
        handle.className = 'bluesky-handle';
        handle.textContent = '@' + author.handle;
        authorInfo.appendChild(handle);

        authorLink.appendChild(authorInfo);
        header.appendChild(authorLink);

        // Date link
        const dateLink = document.createElement('a');
        dateLink.href = postUrl;
        dateLink.target = '_blank';
        dateLink.rel = 'noopener noreferrer';
        dateLink.className = 'bluesky-post-date';
        dateLink.textContent = formatDate(record.createdAt);
        header.appendChild(dateLink);

        article.appendChild(header);

        // Content section
        const content = document.createElement('div');
        content.className = 'bluesky-post-content';

        // Post text
        const textP = document.createElement('p');
        appendTextWithLinks(record.text || '', textP);
        content.appendChild(textP);

        // Embedded images
        if (post.embed && post.embed.images && post.embed.images.length > 0) {
            const imagesDiv = document.createElement('div');
            imagesDiv.className = 'bluesky-post-images';

            post.embed.images.forEach(img => {
                const imgEl = document.createElement('img');
                imgEl.src = img.thumb || img.fullsize;
                imgEl.alt = img.alt || 'Post image';
                imgEl.className = 'bluesky-post-image';
                imgEl.loading = 'lazy';
                imagesDiv.appendChild(imgEl);
            });

            content.appendChild(imagesDiv);
        }

        // External link card
        if (post.embed && post.embed.external) {
            const external = post.embed.external;
            const linkCard = document.createElement('a');
            linkCard.href = external.uri;
            linkCard.target = '_blank';
            linkCard.rel = 'noopener noreferrer';
            linkCard.className = 'bluesky-link-card';

            if (external.thumb) {
                const thumb = document.createElement('img');
                thumb.src = external.thumb;
                thumb.alt = '';
                thumb.className = 'bluesky-link-thumb';
                thumb.loading = 'lazy';
                linkCard.appendChild(thumb);
            }

            const linkInfo = document.createElement('div');
            linkInfo.className = 'bluesky-link-info';

            const linkTitle = document.createElement('span');
            linkTitle.className = 'bluesky-link-title';
            linkTitle.textContent = external.title || external.uri;
            linkInfo.appendChild(linkTitle);

            if (external.description) {
                const linkDesc = document.createElement('span');
                linkDesc.className = 'bluesky-link-description';
                linkDesc.textContent = external.description;
                linkInfo.appendChild(linkDesc);
            }

            linkCard.appendChild(linkInfo);
            content.appendChild(linkCard);
        }

        article.appendChild(content);

        // Footer with stats
        const footer = document.createElement('div');
        footer.className = 'bluesky-post-footer';

        // Heart icon for likes
        const likePath = 'M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z';
        footer.appendChild(createStatLink(postUrl, likePath, post.likeCount || 0));

        // Repost icon
        const repostPath = 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z';
        footer.appendChild(createStatLink(postUrl, repostPath, post.repostCount || 0));

        // Comment icon
        const commentPath = 'M21.99 4c0-1.1-.89-2-1.99-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4-.01-18z';
        footer.appendChild(createStatLink(postUrl, commentPath, post.replyCount || 0));

        article.appendChild(footer);

        return article;
    }

    /**
     * Fetch posts from Bluesky API
     * @returns {Promise<Array>} Array of feed items
     */
    async function fetchBlueskyPosts() {
        const response = await fetch(API_URL);

        if (!response.ok) {
            throw new Error('Bluesky API error: ' + response.status);
        }

        const data = await response.json();
        return data.feed || [];
    }

    /**
     * Initialize the Bluesky feed
     */
    async function initBlueskyFeed() {
        const container = document.getElementById(FEED_CONTAINER_ID);

        if (!container) {
            // Feed container not on this page
            return;
        }

        try {
            const feedItems = await fetchBlueskyPosts();

            // Clear loading message
            container.textContent = '';

            if (feedItems.length === 0) {
                const emptyMsg = document.createElement('p');
                emptyMsg.className = 'bluesky-empty';
                emptyMsg.textContent = 'No recent posts. Follow us on ';

                const link = document.createElement('a');
                link.href = 'https://bsky.app/profile/' + BLUESKY_HANDLE;
                link.target = '_blank';
                link.textContent = 'Bluesky';
                emptyMsg.appendChild(link);
                emptyMsg.appendChild(document.createTextNode('!'));

                container.appendChild(emptyMsg);
                return;
            }

            // Filter out replies (only show original posts)
            const originalPosts = feedItems.filter(function(item) {
                return !item.post.record.reply;
            });

            // Create posts container
            const postsDiv = document.createElement('div');
            postsDiv.className = 'bluesky-posts';

            // Render each post
            originalPosts.forEach(function(item) {
                postsDiv.appendChild(renderBlueskyPost(item));
            });

            container.appendChild(postsDiv);

            // Add follow button
            const followDiv = document.createElement('div');
            followDiv.className = 'bluesky-follow';

            const followLink = document.createElement('a');
            followLink.href = 'https://bsky.app/profile/' + BLUESKY_HANDLE;
            followLink.target = '_blank';
            followLink.rel = 'noopener noreferrer';
            followLink.className = 'btn-outline';
            followLink.textContent = 'Follow @' + BLUESKY_HANDLE;

            followDiv.appendChild(followLink);
            container.appendChild(followDiv);

        } catch (error) {
            console.error('Error loading Bluesky feed:', error);

            // Clear container and show error
            container.textContent = '';

            const errorMsg = document.createElement('p');
            errorMsg.className = 'bluesky-error';
            errorMsg.textContent = 'Unable to load posts. Visit us on ';

            const link = document.createElement('a');
            link.href = 'https://bsky.app/profile/' + BLUESKY_HANDLE;
            link.target = '_blank';
            link.textContent = 'Bluesky';
            errorMsg.appendChild(link);
            errorMsg.appendChild(document.createTextNode('.'));

            container.appendChild(errorMsg);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBlueskyFeed);
    } else {
        initBlueskyFeed();
    }
})();
