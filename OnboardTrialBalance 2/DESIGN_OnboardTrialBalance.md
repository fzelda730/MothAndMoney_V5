# Design System Strategy: The Digital Atelier

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Digital Atelier."** 

Unlike standard accounting software that feels cold and bureaucratic, this system treats the general ledger as a pristine, high-end gallery space. We are moving beyond the "spreadsheet" aesthetic to create an environment that feels as intentional as a curated exhibition. 

To break the "template" look, we employ **Intentional Asymmetry**. We utilize the `20` (7rem) and `24` (8.5rem) spacing tokens to create sweeping "white space lungs"—areas where the UI breathes deeply, pushing content into elegant, off-center compositions. We eschew rigid grids in favor of a "floating" layout where financial data feels like art objects on a gallery wall.

## 2. Colors & Surface Philosophy
The palette is grounded in the "Canvas" (`#FFFFFF`) to mimic the artist's starting point, with high-contrast "Text" (`#1A1A1A`) for authoritative legibility.

### The "No-Line" Rule
Standard 1px borders are strictly prohibited for sectioning. Definition must be achieved through **Background Color Shifts**. 
- A `surface-container-low` (`#f3f3f3`) sidebar sitting against a `surface` (`#f9f9f9`) main stage.
- Use `surface-container-highest` (`#e2e2e2`) only for small, high-density interactive zones.
- Boundaries are felt through the change in "paper weight," not drawn with a pen.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked, fine-art papers. 
- **Base Layer:** `surface` (`#f9f9f9`)
- **Main Content Card:** `surface-container-lowest` (`#ffffff`)
- **Nested Controls:** `surface-container` (`#eeeeee`)
By nesting these tiers, you create depth that feels structural rather than decorative.

### The "Glass & Gradient" Rule
To elevate the "Streamlit" feel, floating elements (like popovers or active navigation states) should utilize **Glassmorphism**. Apply a semi-transparent `surface-container-low` with a `backdrop-blur` of 12px. 
For primary CTAs, use a subtle linear gradient from `primary` (`#154212`) to `primary-container` (`#2d5a27`) at a 135-degree angle. This adds a "silk finish" to the forest green, suggesting professional polish.

## 3. Typography: Editorial Authority
We pair the geometric precision of **Manrope** for high-level structure with the utilitarian clarity of **Inter** for data.

- **Display & Headlines (Manrope):** These are your "Gallery Titles." Use `display-lg` with `tight` letter-spacing for large-scale totals. This conveys a sense of architectural permanence.
- **Body & Labels (Inter):** These are your "Curatorial Notes." `body-md` and `label-sm` handle the heavy lifting of financial ledger entries. 
- **Contrast as Hierarchy:** Set titles in `on_surface` (#1a1c1c) and secondary metadata in `on_secondary_container` (#636262). This creates a rhythmic reading experience that guides the eye naturally through complex ledgers.

## 4. Elevation & Depth
We reject the "drop shadow" of the early 2010s. Depth is organic.

- **The Layering Principle:** A `surface-container-lowest` card placed on a `surface-container-low` background creates a "soft lift" that is felt rather than seen.
- **Ambient Shadows:** For floating modals, use a shadow with a 40px blur, 0% spread, and 6% opacity using the `on-surface` color. This mimics natural light falling across a studio.
- **The "Ghost Border" Fallback:** If a divider is required for accessibility (e.g., in high-density tables), use the `outline-variant` token at **15% opacity**. It should be a whisper, not a statement.
- **Glassmorphism:** Use semi-transparent layers for the sidebar to allow the "Canvas" color to bleed through, ensuring the navigation feels integrated into the workspace.

## 5. Components

### Sidebar Navigation
- **Styling:** Use `surface-container-low`. No border on the right edge.
- **Active State:** A `primary-fixed-dim` (`#a1d494`) soft-glow background with `md` (0.375rem) rounded corners.

### Clean Data Tables
- **Rule:** Forbid horizontal and vertical divider lines. 
- **Separation:** Use `spacing-3` (1rem) of vertical padding between rows. 
- **Row Hover:** Shift background to `surface-container-high` (`#e8e8e8`) with a `sm` transition.

### Simple Upload Areas (The "Drop Zone")
- **Styling:** A large `surface-container-lowest` area with a `dashed` "Ghost Border" (10% opacity `outline`).
- **Interaction:** On drag-over, transition the background to `primary-fixed` (`#bcf0ae`) at 20% opacity.

### Buttons & Chips
- **Primary Button:** `primary` background, `on-primary` text. `sm` (0.125rem) roundedness for a sharper, more professional "architectural" edge.
- **Status Chips:** For "Paid" or "Pending," use `primary-fixed-dim` for positive and `tertiary-fixed-dim` for warnings. Keep text in `on-primary-fixed-variant` to maintain a muted, high-end tone.

### Input Fields
- **Styling:** Minimalist bottom-border only, using `outline-variant` at 40%. 
- **Focus:** Transition the bottom border to `primary` (`#154212`) and 2px thickness.

## 6. Do's and Don'ts

### Do
- **DO** use asymmetric margins. For example, give a table a 12 (4rem) left margin and a 16 (5.5rem) right margin to create an editorial feel.
- **DO** use `display-sm` for large financial summaries; let the numbers be the hero of the composition.
- **DO** prioritize "white space as a feature." If a page feels crowded, increase spacing tokens rather than adding borders.

### Don't
- **DON'T** use pure black (#000000) for text. Always use `on_surface` (#1a1c1c) to keep the "ink" from feeling too harsh against the "canvas."
- **DON'T** use 100% opaque borders. They create "visual noise" that distracts the artist from their data.
- **DON'T** use standard "system blue" for links. Use the `primary-container` (`#2d5a27`) to keep the brand cohesive and organic.
- **DON'T** use heavy, dark shadows. If a component doesn't look elevated through color shifts alone, use an Ambient Shadow at <8% opacity.