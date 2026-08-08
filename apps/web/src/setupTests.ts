import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView (used by MessageArea's scroll-to-latest behavior,
// PBI-04-02) — stub it so component tests don't need to know about this environment gap.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
