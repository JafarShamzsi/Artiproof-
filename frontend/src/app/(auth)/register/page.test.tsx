import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import RegisterPage from "./page";

const { apiFetch, session, params, update } = vi.hoisted(() => {
  const update = vi.fn();
  return {
    apiFetch: vi.fn(), update,
    session: { status: "authenticated", update },
    params: { query: "invite=recipient-token" },
  };
});
vi.mock("@/lib/api", () => ({ apiFetch, backendUrl: (path: string) => path }));
vi.mock("next-auth/react", () => ({ signIn: vi.fn(), useSession: () => session }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(params.query) }));

beforeEach(() => {
  vi.resetAllMocks();
  session.status = "authenticated";
  params.query = "invite=recipient-token";
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ organization_id: "org", name: "Test Lab", role: "member" }) });
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: "accepted" }) });
});

function pendingRefresh() {
  let resolve!: (value: unknown) => void;
  const promise = new Promise((done) => { resolve = done; });
  update.mockImplementationOnce(() => {
    session.status = "loading";
    return promise;
  });
  return async (value: unknown) => {
    await act(async () => {
      session.status = "authenticated";
      resolve(value);
      await promise;
    });
  };
}

async function accept() {
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  const button = await screen.findByRole("button", { name: "Accept invitation and join team" });
  await act(async () => { fireEvent.click(button); });
  expect(update).toHaveBeenCalled();
}

it.each([false, true])("preserves consent through the real loading transition (refresh fails: %s)", async (fails) => {
  const finish = pendingRefresh();
  const view = render(<RegisterPage />);
  await accept();
  view.rerender(<RegisterPage />);
  expect(screen.queryByRole("button", { name: "Accept invitation and join team" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Checking session");
  await finish(fails ? null : { user: { organizationId: "org" } });
  view.rerender(<RegisterPage />);
  if (fails) {
    expect(await screen.findByRole("alert")).toHaveTextContent("session refresh failed");
    const finishRetry = pendingRefresh();
    fireEvent.click(screen.getByRole("button", { name: "Retry session refresh" }));
    view.rerender(<RegisterPage />);
    await finishRetry({ user: { organizationId: "org" } });
    view.rerender(<RegisterPage />);
  }
  expect(await screen.findByText(/Invitation accepted/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Continue to team" })).toHaveAttribute("href", "/team");
  expect(apiFetch).toHaveBeenCalledTimes(2);
  expect(update).toHaveBeenCalledWith({ refreshAccount: true });
});

it.each(["logout", "token"])("clears accepted confirmation after %s", async (change) => {
  update.mockResolvedValue({ user: { organizationId: "org" } });
  const view = render(<RegisterPage />);
  await accept();
  expect(await screen.findByRole("link", { name: "Continue to team" })).toBeInTheDocument();
  if (change === "logout") session.status = "unauthenticated";
  else params.query = "invite=different-token";
  view.rerender(<RegisterPage />);
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
  session.status = "authenticated";
  view.rerender(<RegisterPage />);
  expect(screen.getByRole("button", { name: "Review invitation" })).toBeInTheDocument();
  expect(apiFetch).toHaveBeenCalledTimes(2);
});

it("resets reviewed consent on token changes", async () => {
  const view = render(<RegisterPage />);
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  expect(await screen.findByText("Test Lab")).toBeInTheDocument();
  params.query = "invite=different-token";
  view.rerender(<RegisterPage />);
  expect(screen.getByRole("button", { name: "Review invitation" })).toBeInTheDocument();
  expect(screen.queryByText("Test Lab")).not.toBeInTheDocument();
  expect(apiFetch).toHaveBeenCalledTimes(1);
});

it("discards pending consent on actual authentication loss, even if refresh completes later", async () => {
  const finish = pendingRefresh();
  const view = render(<RegisterPage />);
  await accept();
  session.status = "unauthenticated";
  view.rerender(<RegisterPage />);
  expect(screen.getByRole("button", { name: "Create Account" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Review invitation" })).not.toBeInTheDocument();
  await finish({ user: { organizationId: "org" } });
  view.rerender(<RegisterPage />);
  expect(screen.getByRole("button", { name: "Review invitation" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
});

it("does not authorize initial loading or change standard signup without an invitation", () => {
  session.status = "loading";
  const view = render(<RegisterPage />);
  expect(screen.queryByRole("button", { name: "Review invitation" })).not.toBeInTheDocument();
  params.query = "";
  view.rerender(<RegisterPage />);
  expect(screen.getByRole("button", { name: "Create Account" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Team invitation" })).not.toBeInTheDocument();
  expect(apiFetch).not.toHaveBeenCalled();
});
