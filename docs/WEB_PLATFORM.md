# Public Web Platform

## Browser baseline

The public UI is a dependency-free HTML/CSS/JavaScript application served by FastAPI.

Supported target:
- Current Chrome/Chromium, Firefox, Safari and Edge releases.
- Desktop, tablet and mobile layouts.
- Pointer, touch and keyboard interaction.

The UI intentionally avoids framework/runtime dependencies. Browser-facing GitHub credentials are never present.

## Accessibility

Implemented:
- semantic headings, landmarks and forms
- skip link
- visible keyboard focus
- keyboard-operable controls
- live status regions for asynchronous search/graph state
- accessible structured graph fallback
- graph SVG label/title information
- reduced-motion support
- visible labels instead of placeholder-only form semantics

The focus treatment follows WCAG guidance that keyboard-operable interfaces need a visible focus indicator.

## Data handling

Public discovery:
- GitHub data only
- short public cache lifetime
- source and generated timestamp surfaced to users
- upstream failures produce retryable UI states

Private analyst workspace:
- requires the private API key
- workspace notes are never returned by public discovery/profile/graph endpoints
- bundle exports are explicitly private

## Exports

Public exports include schema/source/timestamp metadata where applicable:
- CSV
- JSON
- Markdown
- SVG graph
- engineer profile JSON/Markdown
- graph JSON/Markdown

Private investigation bundles include evidence, notes and timeline events and are only available through authenticated workspace routes.

## Graph behavior

The graph supports:
- community filtering
- centrality filtering
- node search
- relationship-type filtering
- zoom and pan
- node dragging
- neighborhood highlighting
- shortest-path exploration
- community summaries
- centrality ranking
- progressive node rendering
- structured fallback data

The server also accepts bounded graph filters so client-side filtering is not the security boundary.

## Operational signals

The public API exposes:
- request correlation IDs
- GitHub rate-limit visibility
- request/search/profile/graph counters
- freshness timestamps
- retry behavior for upstream failures
- safe public-data cache headers
