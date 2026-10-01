# UI Theme Fixes for Vanilla Elements

## Scope
- Fixed missing `.button.ghost` CSS class that was causing some buttons (like the download buttons for scripts) to render with the browser's default white background, making text unreadable against the dark theme.
- Added base `background: transparent` and `color: inherit` reset to `.button` to ensure consistent button rendering.
- Added `color-scheme: dark;` to the `:root` to instruct browsers to use native dark-mode styling for vanilla HTML elements.
- Added explicit WebKit styling for the `<audio>` player (`::-webkit-media-controls-panel`) to make its background seamlessly match the application's dark muted theme (`--bg-muted`).

## Architectural Decisions
- Used `color-scheme` instead of attempting to completely rebuild the audio player UI from scratch, which provides immediate, accessible, and lightweight styling out of the box while staying true to the "vanilla" requirement.

## Next Steps
None at this time for these components.
