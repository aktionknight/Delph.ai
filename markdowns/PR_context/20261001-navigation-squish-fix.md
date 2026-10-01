# Scope
Fix an issue where navigation elements (workflow track, campaign tabs) get squished vertically when the fixed-height scrollable layouts force the main content flex container to shrink its children.

# Implemented Changes
- Added `.main-content > * { flex-shrink: 0; }` in `globals.css` to prevent any direct children of the main content area from being compressed by flexbox layout calculations.

# Architectural Decisions
- Setting `flex-shrink: 0` is the standard solution for flex children that contain critical UI (like text or interactive tabs) that should never be distorted to satisfy a flex container's constraints. This allows `.main-content`'s `overflow-y: auto` to properly handle any overflow instead of visually corrupting the UI.

# Next Steps
- Validate that the navigation tabs render at full height alongside the scrollable content layouts.
