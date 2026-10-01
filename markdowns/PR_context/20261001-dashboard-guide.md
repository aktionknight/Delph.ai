# Scope
- Removed the large `.hero` section with the Rocket logo orbit diagram from the main overview dashboard.
- Replaced it with an interactive, toggleable "How to use Delph.ai" guide section that explains the application's flow.

# Implemented Changes
- **Interactive Guide:** Imported `useState` into `launchpad.tsx` and implemented a boolean toggle state `showGuide`.
- **Hero Removal:** Deleted the static `<section className="hero">` block which previously occupied significant vertical space on the dashboard.
- **Workflow Documentation:** When toggled open, the guide uses `<details>` and `<summary>` tags to explain the 5 core steps of the application:
  1. Define the Brand Brain
  2. Create a Campaign Strategy
  3. Build the Timeline
  4. Content Canvas & Generation
  5. Human Approval & Experiments
- **Aesthetics:** Housed the guide in a `.panel` with a `--accent` border highlight to visually anchor the instructions without overwhelming the default empty state.

# Architectural Decisions
- Used native HTML `<details>` elements for the list inside the guide to allow users to open/close specific steps natively without needing complex React array state management for each accordion item.

# Verification Results
- The dashboard is immediately cleaner. The user's focus is pushed directly to the metrics and campaign list.
- Toggling the guide smoothly reveals the instructional copy.

# Limitations
- None. 

# Next Steps
- Verify if any other placeholder landing graphics (like the empty states) require adjustments.
