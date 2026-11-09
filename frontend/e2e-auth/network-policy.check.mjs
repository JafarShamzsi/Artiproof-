// Node-only mocked policy checks. Not collected by Playwright; no browser/URL contact.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("./network-policy.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const sandbox = { exports: {}, URL };
vm.runInNewContext(compiled, sandbox);
const { allowedDestination, installNetworkGuard, guardAPIRequest, assertBrowserExecutionAllowed } = sandbox.exports;

test("only exact app HTTP origins and dev WebSocket are allowed", () => {
  for (const url of ["http://127.0.0.1:3203/login", "http://127.0.0.1:8203/api/auth/me"]) assert.equal(allowedDestination(url), true);
  for (const url of ["https://external.invalid/", "http://127.0.0.1:9999/", "http://localhost:3203/", "http://127.0.0.1:3203.evil.invalid/", "http://user:pass@127.0.0.1:3203/", "file:///x", "garbage"]) assert.equal(allowedDestination(url), false);
  assert.equal(allowedDestination("ws://127.0.0.1:3203/hmr", true), true);
  assert.equal(allowedDestination("ws://127.0.0.1:8203/", true), false);
  assert.equal(allowedDestination("wss://external.invalid/", true), false);
});

test("known redirect escape forces hold before installing any context routes", async () => {
  let touchedContext = false;
  await assert.rejects(installNetworkGuard({
    route: () => { touchedContext = true; }, routeWebSocket: () => { touchedContext = true; },
  }, []), /Browser execution hold.*redirects bypass routing callbacks/);
  assert.equal(touchedContext, false);
});

test("browser hold is unconditional and has no argument/environment permission switch", () => {
  sandbox.process = { env: { QA_AUTH_ALLOW_BROWSER: "1", APPROVED: "true" } };
  for (const argument of [undefined, true, { approved: true, allowBrowser: true }]) {
    assert.throws(() => assertBrowserExecutionAllowed(argument), /independent containment design.*explicit manager permission.*later reviewed change/);
  }
});

test("direct auth Playwright config refuses before defineConfig can execute", () => {
  const config = readFileSync(new URL("../playwright.auth.config.ts", import.meta.url), "utf8");
  const javascript = ts.transpileModule(config, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  let defined = false;
  const configSandbox = {
    exports: {}, process: { env: { QA_AUTH_ARTIFACTS: "synthetic", QA_AUTH_ALLOW_BROWSER: "1" } },
    require(name) {
      if (name === "@playwright/test") return { defineConfig: () => { defined = true; }, devices: {} };
      if (name === "node:path") return {};
      if (name === "./e2e-auth/network-policy") return sandbox.exports;
      throw new Error(`Unexpected mocked import ${name}`);
    },
  };
  assert.throws(() => vm.runInNewContext(javascript, configSandbox), /Browser execution hold/);
  assert.equal(defined, false);
});

test("standalone API request rejects external target before dispatch", () => {
  let dispatched = false;
  const client = guardAPIRequest({ post: () => { dispatched = true; } });
  assert.throws(() => client.post("https://external.invalid/"), /before dispatch/);
  assert.equal(dispatched, false);
});

test("standalone API keeps real local method and disables redirect following", () => {
  let called = false;
  const client = guardAPIRequest({ post(url, options) {
    assert.equal(url, "http://127.0.0.1:8203/api/auth/login");
    assert.equal(options.maxRedirects, 0);
    assert.equal(options.data, "unchanged-body");
    called = true;
  } });
  client.post("http://127.0.0.1:8203/api/auth/login", { data: "unchanged-body", maxRedirects: 10 });
  assert.equal(called, true);
});
