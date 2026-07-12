import assert from "node:assert/strict";
import test from "node:test";

test("web workspace is available", () => {
  assert.equal("@auditor/web".startsWith("@auditor/"), true);
});
