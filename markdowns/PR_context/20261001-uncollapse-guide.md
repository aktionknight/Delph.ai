# Scope
- Refactored the interactive Dashboard App Guide to show all steps plainly without requiring user expansion.

# Implemented Changes
- **Visibility:** Replaced native `<details>` and `<summary>` HTML elements in `apps/web/components/launchpad.tsx` with standard `<div className="guide-step">` blocks. All 5 steps (Define Brand Brain, Strategy, Timeline, Generation, Approval) are now immediately visible when the guide is toggled.
- **Styling:** Updated `.history-list details` rules in `globals.css` to also target `.guide-step`, preserving the intended visual separation and padding for the list of steps.

# Architectural Decisions
- Used simple `div` tags because the user did not realize the native `<details>` elements required clicking to expand. Presenting instructions outright optimizes for quick reading in this context.

# Verification Results
- Clicking "How to use Delph.ai" instantly renders all 5 steps stacked cleanly.

# Limitations
- None.

# Next Steps
- None.
