import type { APIRequestContext, BrowserContext } from "@playwright/test";

const httpOrigins = new Set(["http://127.0.0.1:3203", "http://127.0.0.1:8203"]);
const websocketOrigins = new Set(["ws://127.0.0.1:3203"]); // Next dev only

export function assertBrowserExecutionAllowed(): never {
  throw new Error("Browser execution hold: Playwright 1.60 automatic external redirects bypass routing callbacks. Requires independent containment design and explicit manager permission in a later reviewed change; no bypass switch.");
}

export function allowedDestination(value: string, websocket = false): boolean {
  try {
    const url = new URL(value);
    return !url.username && !url.password
      && (websocket ? websocketOrigins : httpOrigins).has(url.origin);
  } catch { return false; }
}

/** Standalone API clients do not inherit browser routing. Validate each target
 * before calling the real client; disable automatic redirect dispatch entirely.
 */
export function guardAPIRequest(client: APIRequestContext): APIRequestContext {
  const methods = new Set(["get", "post", "put", "patch", "delete", "head", "fetch"]);
  return new Proxy(client, {
    get(target, property) {
      const value = Reflect.get(target, property);
      if (methods.has(String(property))) {
        return (destination: string, options: Record<string, unknown> = {}) => {
          const url = typeof destination === "string"
            ? new URL(destination, "http://127.0.0.1:3203").href : "";
          if (!allowedDestination(url)) throw new Error("QA-01 API destination rejected before dispatch");
          return value.call(target, url, { ...options, maxRedirects: 0 });
        };
      }
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}

/** HELD: routing is NOT egress containment. Installed Playwright 1.60 skips
 * the route callback for automatic redirected requests, so denial can stay empty
 * while an external request escapes. No permission/environment override exists.
 */
export async function installNetworkGuard(context: BrowserContext, denied: string[]) {
  assertBrowserExecutionAllowed();
  await context.route("**/*", async route => {
    if (allowedDestination(route.request().url())) {
      await route.continue();
    } else {
      denied.push("HTTP request rejected before dispatch"); // no tokens/URLs in evidence
      await route.abort("blockedbyclient");
    }
  });
  await context.routeWebSocket("**/*", socket => {
    if (allowedDestination(socket.url(), true)) {
      socket.connectToServer();
    } else {
      denied.push("WebSocket rejected before connectToServer");
      socket.close({ code: 1008, reason: "QA-01 destination not allowlisted" });
    }
  });
}
