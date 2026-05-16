import "@testing-library/jest-dom/vitest";

class ResizeObserverMock {
  observe() {}

  unobserve() {}

  disconnect() {}
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = ResizeObserverMock;
}

if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {
      return false;
    },
  });
}

if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = function scrollIntoView() {};
}

const originalGetComputedStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = (element, pseudoElt) => {
  if (pseudoElt) {
    return {
      getPropertyValue: () => "",
      overflow: "auto",
      overflowX: "auto",
      overflowY: "auto",
      width: "0px",
      height: "0px",
    };
  }
  return originalGetComputedStyle(element);
};
