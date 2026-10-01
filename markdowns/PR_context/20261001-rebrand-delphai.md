# Scope
- Rebranded the UI from "Campaign Launchpad" to "Delph.ai" globally.
- Replaced the default Lucide `<Rocket>` logo icon with the custom user-provided `logo.png` (formerly `Abstract Teal Ribbon Play Emblem.png`).

# Implemented Changes
- **Logo Replacement:** Renamed the uploaded custom logo in `public/` to `logo.png` for simplicity. Updated `apps/web/components/launchpad.tsx` to use an `<img>` tag rendering `logo.png` instead of the `<Rocket>` icon inside the `.logo-mark` container.
- **Brand Text Swap:** Changed textual references:
  - `launchpad.` -> `Delph.ai` in the main sidebar logo text (`launchpad.tsx`).
  - "Campaign Launchpad" -> "Delph.ai" in the application footer (`launchpad.tsx`).
  - "Sign in to Campaign Launchpad" -> "Sign in to Delph.ai" in the account gate (`account.tsx`).
  - `title` metadata in `apps/web/app/layout.tsx` updated to `Delph.ai — From idea to impact`.

# Architectural Decisions
- Used a standard HTML `<img>` with `width={22} height={22}` and `objectFit: 'contain'` rather than Next.js `<Image>` for the logo to avoid requiring `next/image` domain configurations if hosted statically, matching the simplicity of the previous SVG icon.

# Verification Results
- All instances of the old branding in the UI have been replaced.
- The new logo renders within the existing layout container without distortion.

# Limitations
- None.

# Next Steps
- Validate if any email templates or external marketing assets (if added in the future) still use the old brand name.
