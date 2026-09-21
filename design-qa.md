# Design QA — Agent-first patient home

- Source visual truth: `C:/Users/liuch/AppData/Local/Temp/codex-clipboard-00922fd2-b36b-42c5-9dbc-70d01162d73f.jpg`
- Implementation: `http://127.0.0.1:4173/home?preview=1`
- Implementation screenshot evidence: Codex in-app Browser tab 2 captures from this QA session (mobile and desktop; the browser surface does not expose a persistent screenshot filepath).
- Source pixels: 1260 × 2800. The supplied screenshot is a tall mobile reference and was used for information rhythm, not literal product/content cloning.
- Implementation pixels/CSS/density: 390 × 844 CSS px at deviceScaleFactor 1; 375 × 667 CSS px at deviceScaleFactor 1; 1280 × 720 CSS px at deviceScaleFactor 1.
- State: authenticated patient-home visual preview with a next appointment and three available schedules.
- Browser verification: primary input enabled after text entry; a suggested prompt navigated into the AI Assistant with the prompt preserved in the composer; responsive navigation and all semantic controls were present; fresh-tab console check returned no warnings or errors.

## Comparison scope

The reference is directional: it establishes a mobile sequence of compact personal information followed immediately by a prominent AI composer and persistent service navigation. The implementation deliberately retains the project's teal hospital identity, real patient data model, and existing navigation rather than copying the reference's membership, advertising, and growth-task content.

## Full-view comparison evidence

- Mobile 390 × 844: essential status information appears first, followed immediately by the AI identity, agent promise, composer, and suggested prompts. The composer is fully visible before scrolling; the AI Assistant is the emphasized center tab.
- Small mobile 375 × 667: the full composer remains visible above the persistent tab bar with no horizontal overflow or overlapping controls.
- Desktop 1280 × 720: the Agent card occupies the dominant left column; compact tasks and live schedules use the secondary rail. The existing sidebar and top bar remain intact.

## Required fidelity surfaces

- Fonts and typography: the existing Noto Sans SC/PingFang/system stack is preserved. The display heading uses a deliberate 27–45 px responsive scale, dense Chinese line height, and stronger weight; supporting labels remain legible and do not wrap awkwardly in tested viewports.
- Spacing and layout rhythm: mobile uses 9–17 px gutters and 14–24 px section/card rhythm. Desktop uses a 1120 px content measure and a 1.65/.78 main-to-rail ratio, making the Agent visibly primary. Card radii and elevation are consistent with the current product shell.
- Colors and tokens: the implementation maps the reference's cool medical palette to the established Wenrun teal system. Text/background contrast is maintained; amber is reserved for the emergency notice and green for online state.
- Image quality and asset fidelity: no raster imagery is required in the redesigned experience. The reference's membership avatar and promotional banner are intentionally omitted because they do not belong to this hospital Agent flow. All visible icons use the project's Lucide-based icon component; no placeholder imagery, emoji, custom SVG, or fake illustration is used.
- Copy and content: membership/growth copy was replaced with patient actions: symptom guidance, schedule lookup, booking, and appointment review. The AI limitation is stated next to the composer.
- Interaction and accessibility: form submit, Enter-to-send handoff, task shortcuts, schedule prompts, and direct navigation are wired. Controls have semantic labels, focus styling, disabled state, reduced-motion handling, and mobile targets of at least 42–48 px in the primary flow.

## Focused-region comparison evidence

The mobile source composer region and the implementation composer were inspected at comparable on-screen scale. Both use a highly visible rounded input outline, a distinct send control, nearby quick prompts, and a persistent service nav. The implementation intentionally removes microphone/camera controls because those capabilities do not exist in the current product.

## Findings

No actionable P0, P1, or P2 findings remain.

## Comparison history

1. First desktop pass — P2: the home header repeated the brand and emergency control already present in the desktop shell, weakening the Agent hierarchy.
   - Fix: hide the home-specific brand row on desktop while retaining it on mobile.
   - Post-fix evidence: 1280 × 720 capture shows the greeting and appointment strip leading directly into the Agent card, with no duplicated header controls.
2. Mobile passes — no P0/P1/P2 findings at 390 × 844 or 375 × 667. The composer remained visible, the AI tab remained emphasized, and no layout collision was observed.

## Open questions

- None blocking. Camera and voice actions from the reference were not implemented because the existing product has no such capabilities.

## Implementation checklist

- [x] Agent is the dominant first-screen action.
- [x] Next appointment stays visible without overtaking the Agent.
- [x] Mobile composer is visible above the fold on a 375 × 667 viewport.
- [x] Desktop expands into an Agent-first two-column layout.
- [x] Quick tasks enter the Agent with intent-prefilled prompts.
- [x] Lint, tests, production build, browser console, and responsive layout checks pass.

## Follow-up polish

- P3: after real usage data is available, reorder the three suggested prompts by frequency.

final result: passed
