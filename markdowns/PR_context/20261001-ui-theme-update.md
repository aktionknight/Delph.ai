# Scope
Updated the web app's UI theme to use dark greytones and white-teal accents instead of the previous blue/indigo theme.

# Implemented Changes
- Replaced the primary background variables in `globals.css` with dark greys (e.g. #121212, #1a1a1a).
- Replaced `--accent` variables with teal shades (Teal 400 `#2dd4bf` and Teal 500 `#14b8a6`).
- Standardized all button components (`.button`, `.button.primary`, `.button.secondary`, `.button.dark`) with modern border radii (8px), transitions, and hover glow effects.
- Updated `.nav-link` and `.campaign-card` with enhanced micro-animations (transformations and inset shadows).
- Replaced hardcoded indigo colors (`#818cf8`, `#1e1b4b`) in `.campaign-art`, `.eyebrow`, and other classes with `var(--accent)` or appropriate teal gradients.
- Added Next.js `next/font/google` Inter font to `layout.tsx` to standardize modern typography across the app.

# Architectural Decisions
- Migrated away from plain blue-black hexes in favor of a true "dark mode" palette with strong teal accents to match the "white-teal" requirement.
- Added `--shadow-*` variables to `:root` to ensure standard shadow styles for components.
- Kept the vanilla CSS approach instead of Tailwind as per the existing codebase architecture.

# Verification Results
- No hardcoded indigo/blue colors remain in the `.tsx` or `.css` files. All components utilize the unified CSS variables.

# Limitations
- If any dynamic styles via Javascript previously relied on the hex codes for indigo, they might not update automatically, though none were found.

# Next Steps
- Verify the new UI changes locally with the dev server.
- Ensure that the teal accents meet contrast accessibility standards.
