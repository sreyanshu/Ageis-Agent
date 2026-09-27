# Aegis UX Quality Dimension & Objective Heuristics

## 1. Objective Signals vs Subjective AI

Aegis separates objective, verifiable UX defects from subjective opinions.

### Evaluated Objective Heuristics:
1. **Unlabeled Interactive Controls**: Buttons, inputs, and anchor links lacking inner text, `aria-label`, and `title`.
2. **Dead-End Navigation**: Anchor links pointing to `href="#"` or empty strings without action handlers.
3. **Heading Hierarchy Skips**: Unstructured jumps in heading levels (e.g. `<h1>` directly to `<h4>`).
4. **Journey Interaction Friction**: Multi-step user journeys exceeding threshold step counts (>12 steps) or containing repetitive cycles.

Each finding is recorded with code snippets, element selectors, and remediation guidance.
