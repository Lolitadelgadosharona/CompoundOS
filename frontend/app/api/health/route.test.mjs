import assert from "node:assert/strict";
import { test } from "vitest";

import { GET } from "./route.ts";

test("GET returns the web health response", async () => {
  const response = GET();

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: "ok", service: "web" });
});
