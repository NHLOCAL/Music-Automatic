import { describe, expect, it } from "vitest";

import { antTheme } from "./antdTheme";

describe("antTheme", () => {
  it("keeps the warm desktop palette requested for the Ant Design provider", () => {
    expect(antTheme.token.colorPrimary).toBe("#225555");
    expect(antTheme.token.colorText).toBe("#51463B");
    expect(antTheme.token.colorBgBase).toBe("#FAFAEE");
    expect(antTheme.token.borderRadius).toBe(18);
    expect(antTheme.token.lineWidth).toBe(2);
    expect(antTheme.components.Button.primaryShadow).toBe("none");
    expect(antTheme.components.Modal.boxShadow).toBe("none");
    expect(antTheme.components.Select.optionSelectedBg).toBe("#CBC4AF");
  });
});
