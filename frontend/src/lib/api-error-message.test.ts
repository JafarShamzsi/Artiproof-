import { describe, expect, it } from "vitest";
import { apiErrorMessage } from "./api-error-message";

describe("apiErrorMessage", () => {
  it.each([
    [" plain message ", "plain message"],
    [{ detail: "Rejected" }, "Rejected"],
    [{ detail: { message: "Quota reached", upgrade_url: "https://untrusted.invalid" } }, "Quota reached"],
    [{ message: "Readable" }, "Readable"],
    [{ detail: [{ msg: "Invalid input", input: "private" }, { msg: "Required" }] }, "Invalid input; Required"],
    [{ detail: [{ msg: {} }, null, "bad"] }, "Fallback"],
    [{ detail: { message: {} } }, "Fallback"],
    [{ detail: { token: "private" } }, "Fallback"],
    [{ detail: "  " }, "Fallback"],
    [null, "Fallback"], [undefined, "Fallback"], [42, "Fallback"], [false, "Fallback"],
    [{ detail: { detail: { message: "Not recursive" } } }, "Fallback"],
  ])("normalizes only supported fields: %j", (value, expected) => {
    expect(apiErrorMessage(value, "Fallback")).toBe(expected);
  });

  it("bounds text and validation count without dumping raw inputs", () => {
    expect(apiErrorMessage({ detail: "x".repeat(2000) }, "Fallback")).toHaveLength(500);
    expect(apiErrorMessage({ detail: Array.from({ length: 100 }, () => ({ msg: "bad", input: "private" })) }, "Fallback"))
      .toBe("bad; bad; bad");
  });

  it("returns markup as plain text, not interpreted HTML", () => {
    expect(apiErrorMessage({ detail: "<b>Rejected</b>" }, "Fallback")).toBe("<b>Rejected</b>");
  });
});
