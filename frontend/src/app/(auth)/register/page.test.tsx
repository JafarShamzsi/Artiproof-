import { useEffect } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SessionProvider, useSession } from "next-auth/react";
import type { Session } from "next-auth";
import RegisterPage from "./page";

// Override the shared unit setup: this suite exercises the installed client.
vi.unmock("next-auth/react");
const { params } = vi.hoisted(() => ({ params: { query: "invite=recipient-token" } }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(params.query) }));

function account(id: string, organizationId: string | null = null): Session {
  return { user: { id, role: "researcher", organizationId }, accessToken: `synthetic-${id}`, expires: "2099-01-01" };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
function response(data: unknown, status = 200) {
  // NextAuth represents an absent session as {}, which fetchData maps to null.
  return new Response(JSON.stringify(data ?? {}), { status, headers: { "Content-Type": "application/json" } });
}

let serverSession: Session | null;
let preview: () => Promise<Response>;
let enrollment: () => Promise<Response>;
let refresh: () => Promise<Response>;
let history: string[];
const http = vi.fn();

function SessionProbe() {
  const { data, status } = useSession();
  const state = `${status}:${data?.user?.id ?? "missing"}:${data?.user?.organizationId ?? "personal"}`;
  useEffect(() => { history.push(state); }, [state]);
  return <output data-testid="session">{state}</output>;
}
function tree(initial: Session | null = account("A")) {
  return <SessionProvider session={initial} refetchOnWindowFocus={false}>
    <RegisterPage /><SessionProbe />
  </SessionProvider>;
}

beforeEach(() => {
  vi.resetAllMocks();
  params.query = "invite=recipient-token";
  serverSession = account("A");
  history = [];
  preview = async () => response({ organization_id: "org", name: "Test Lab", role: "member" });
  enrollment = async () => response({ status: "accepted" });
  refresh = async () => response(account("A", "org"));
  http.mockImplementation(async (url: string, options?: RequestInit) => {
    const path = new URL(url, "http://localhost").pathname;
    if (path === "/api/auth/csrf") return response({ csrfToken: "synthetic-csrf" });
    if (path === "/api/auth/session") return options?.method === "POST" ? refresh() : response(serverSession);
    if (path === "/api/organizations/invites/preview") return preview();
    if (path === "/api/organizations/org/invites/accept") return enrollment();
    throw new Error(`Unexpected HTTP in client integration: ${path}`);
  });
  vi.stubGlobal("fetch", http);
});
afterEach(() => { vi.unstubAllGlobals(); });

function calls(path: string, method = "POST") {
  return http.mock.calls.filter(([url, options]) => new URL(url, "http://localhost").pathname === path && options?.method === method);
}
async function review() {
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  await screen.findByRole("button", { name: "Accept invitation and join team" });
}
async function accept() {
  await review();
  fireEvent.click(screen.getByRole("button", { name: "Accept invitation and join team" }));
}
async function replaceSession(next: Session | null) {
  serverSession = next;
  await act(async () => {
    window.dispatchEvent(new StorageEvent("storage", {
      key: "nextauth.message",
      newValue: JSON.stringify({ event: "session", data: { trigger: "getSession" }, timestamp: Date.now() }),
    }));
  });
  await waitFor(() => expect(screen.getByTestId("session")).toHaveTextContent(
    `${next ? "authenticated" : "unauthenticated"}:${next?.user.id ?? "missing"}`,
  ));
}
function freshConsent() {
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Retry session refresh" })).not.toBeInTheDocument();
  expect(screen.queryByText("Test Lab")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Review invitation" })).toBeInTheDocument();
}

it.each(["reviewed", "accepted", "retry"])("isolates %s consent when authenticated A is replaced by B", async (state) => {
  if (state === "retry") refresh = async () => response(null);
  render(tree());
  expect(calls("/api/organizations/invites/preview")).toHaveLength(0);
  if (state === "reviewed") await review();
  else {
    await accept();
    if (state === "accepted") await screen.findByRole("link", { name: "Continue to team" });
    else await screen.findByRole("button", { name: "Retry session refresh" });
  }
  const acceptsBeforeSwitch = calls("/api/organizations/org/invites/accept").length;
  await replaceSession(account("B"));
  freshConsent();
  expect(calls("/api/organizations/org/invites/accept")).toHaveLength(acceptsBeforeSwitch);
  // B must review and accept explicitly; A's enrollment must not turn this into a retry.
  refresh = async () => response(account("B", "org"));
  await accept();
  expect(await screen.findByRole("link", { name: "Continue to team" })).toHaveAttribute("href", "/team");
  expect(calls("/api/organizations/org/invites/accept")).toHaveLength(acceptsBeforeSwitch + 1);
  expect(history.some((state) => state.startsWith("unauthenticated"))).toBe(false);
});

it.each(["preview", "accept", "refresh", "old-account-refresh"])("ignores A's delayed %s completion after switching to B", async (phase) => {
  const pending = deferred<Response>();
  if (phase === "preview") preview = () => pending.promise;
  else if (phase === "accept") enrollment = () => pending.promise;
  else refresh = () => pending.promise;
  render(tree());
  if (phase === "preview") fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  else await accept();
  const pendingPath = phase === "preview" ? "/api/organizations/invites/preview"
    : phase === "accept" ? "/api/organizations/org/invites/accept" : "/api/auth/session";
  await waitFor(() => expect(calls(pendingPath)).toHaveLength(1));
  await replaceSession(account("B"));
  freshConsent();
  const refreshes = calls("/api/auth/session").length;
  await act(async () => {
    pending.resolve(response(phase === "preview"
      ? { organization_id: "org", name: "Test Lab", role: "member" }
      : phase === "accept" ? { status: "accepted" }
        : account(phase === "old-account-refresh" ? "A" : "B", "org")));
  });
  freshConsent();
  // SessionProvider itself applies a pending update's response. Even when it
  // replaces B with old A, a new consent instance must not inherit A's success.
  expect(screen.getByTestId("session")).toHaveTextContent(
    `authenticated:${phase === "old-account-refresh" ? "A" : "B"}`,
  );
  expect(calls("/api/auth/session")).toHaveLength(refreshes);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it.each([false, true])("retains same-account state through installed update loading (retry: %s)", async (fails) => {
  const pending = deferred<Response>();
  refresh = () => pending.promise;
  render(tree());
  await accept();
  await screen.findByText("Checking session…");
  expect(screen.getByTestId("session")).toHaveTextContent("loading:A:personal");
  expect(screen.queryByRole("button", { name: "Review invitation" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
  await act(async () => { pending.resolve(response(fails ? null : account("A", "org"))); });
  if (fails) {
    expect(await screen.findByRole("alert")).toHaveTextContent("session refresh failed");
    const retry = deferred<Response>();
    refresh = () => retry.promise;
    fireEvent.click(screen.getByRole("button", { name: "Retry session refresh" }));
    await screen.findByText("Checking session…");
    expect(screen.getByTestId("session")).toHaveTextContent("loading:A:personal");
    await act(async () => { retry.resolve(response(account("A", "org"))); });
  }
  expect(await screen.findByRole("link", { name: "Continue to team" })).toHaveAttribute("href", "/team");
  expect(calls("/api/organizations/org/invites/accept")).toHaveLength(1);
  expect(calls("/api/auth/session")).toHaveLength(fails ? 2 : 1);
  expect(JSON.parse(calls("/api/auth/session")[0][1].body as string).data).toEqual({ refreshAccount: true });
  await replaceSession(account("A", "org"));
  expect(screen.getByRole("link", { name: "Continue to team" })).toBeInTheDocument();
});

it.each(["logout", "missing", "empty-id", "token"])("clears accepted state on %s", async (change) => {
  const view = render(tree());
  await accept();
  await screen.findByRole("link", { name: "Continue to team" });
  if (change === "token") {
    params.query = "invite=different-token";
    view.rerender(tree());
    freshConsent();
  } else {
    const missing = { ...account("A"), user: { role: "researcher" } } as Session;
    await replaceSession(change === "logout" ? null : change === "missing" ? missing : account(""));
    expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review invitation" })).not.toBeInTheDocument();
    await replaceSession(account("A"));
    freshConsent();
  }
});

it.each(["logout", "token", "missing"])("discards delayed preview results after %s", async (change) => {
  const pending = deferred<Response>();
  preview = () => pending.promise;
  const view = render(tree());
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  await waitFor(() => expect(calls("/api/organizations/invites/preview")).toHaveLength(1));
  if (change === "token") {
    params.query = "invite=different-token";
    view.rerender(tree());
  } else await replaceSession(change === "logout" ? null : account(""));
  await act(async () => { pending.resolve(response({ organization_id: "org", name: "Test Lab", role: "member" })); });
  expect(screen.queryByText("Test Lab")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
  expect(calls("/api/organizations/org/invites/accept")).toHaveLength(0);
});

it("keeps standard signup without an invitation", () => {
  params.query = "";
  render(tree(null));
  expect(screen.getByRole("button", { name: "Create Account" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Team invitation" })).not.toBeInTheDocument();
  expect(http).not.toHaveBeenCalled();
});

it("does not expose consent actions during initial SessionProvider loading", async () => {
  const pending = deferred<Response>();
  http.mockImplementationOnce(() => pending.promise);
  render(<SessionProvider refetchOnWindowFocus={false}><RegisterPage /><SessionProbe /></SessionProvider>);
  expect(screen.getByTestId("session")).toHaveTextContent("loading:missing:personal");
  expect(screen.getByText("Checking session…")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Review invitation" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
  await act(async () => { pending.resolve(response(account("A"))); });
  freshConsent();
  expect(calls("/api/organizations/invites/preview")).toHaveLength(0);
});
