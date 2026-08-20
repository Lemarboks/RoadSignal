---
name: roadsignal-accessibility-review
description: Review RoadSignal web maps, route selection, incident tables, charts, navigation, location permissions, live-trip alerts, mobile layouts, and status messages for accessibility. Use for WCAG audits, keyboard testing, screen-reader semantics, touch-target checks, forced-colour support, or responsive accessibility fixes.
---

# RoadSignal accessibility review

Audit critical workflows before decorative details.

## Critical path

Test keyboard-only use from skip link through navigation, place suggestions, route selection, trip start, alert response, incident moderation, and notification dismissal.

## Checks

- Provide visible focus and logical order without traps.
- Give comboboxes arrow, Enter, and Escape behaviour with active-descendant state.
- Expose selected routes with `aria-pressed` and a complete text summary.
- Describe maps and charts in text; never require colour or map vision to understand risk.
- Label every filter and announce permission, loading, offline, and error changes.
- Expose trip progress with progressbar values.
- Maintain 44px touch targets and 16px mobile form text.
- Reflow incident tables into labelled mobile records without removing semantics.
- Support reduced motion, forced colours, 200% zoom, 320px width, and safe-area insets.

## Reporting

Prioritise blockers and WCAG AA failures. For every finding, state location, user impact, relevant criterion, remediation, and verification method. Preserve safety disclaimers and product truth.
