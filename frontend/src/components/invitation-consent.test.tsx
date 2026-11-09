import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import RegisterPage from "@/app/(auth)/register/page";

const { apiFetch, signIn, session, update } = vi.hoisted(() => {
  const update = vi.fn();
  return { apiFetch: vi.fn(), signIn: vi.fn(), update, session: { data: { user: { id: "recipient" } }, status: "authenticated", update } };
});
vi.mock("@/lib/api", () => ({ apiFetch, backendUrl: (path: string) => path }));
vi.mock("next-auth/react", () => ({ signIn, useSession: () => session }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("invite=recipient-token") }));

beforeEach(() => {
  vi.clearAllMocks(); session.status = "authenticated";
  update.mockResolvedValue({ user: { id: "recipient", organizationId: "org" } });
});

it("opening an invitation does not accept; review and join are explicit actions", async () => {
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ organization_id: "org", name: "Test Lab", role: "member" }) });
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: "accepted" }) });
  render(<RegisterPage />);
  expect(apiFetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  expect(await screen.findByText("Test Lab")).toBeInTheDocument();
  expect(apiFetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Accept invitation and join team" }));
  expect(await screen.findByText(/Invitation accepted/)).toBeInTheDocument();
  expect(update).toHaveBeenCalledWith({ refreshAccount: true });
  expect(screen.getByRole("link", { name: "Continue to team" })).toHaveAttribute("href", "/team");
  expect(apiFetch).toHaveBeenLastCalledWith("/api/organizations/org/invites/accept", expect.objectContaining({
    method: "POST", body: JSON.stringify({ token: "recipient-token" }),
  }));
});

it.each(["reject", "null", "wrong-org", "wrong-account", "missing-id", "typed-error"])("does not claim success or navigate if session synchronization fails (%s)", async (failure) => {
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ organization_id: "org", name: "Test Lab", role: "member" }) });
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: "accepted" }) });
  if (failure === "reject") update.mockRejectedValueOnce(new Error("Session refresh failed"));
  else update.mockResolvedValueOnce(failure === "null" ? null : failure === "wrong-account"
    ? { user: { id: "different-account", organizationId: "org" } } : failure === "missing-id"
    ? { user: { organizationId: "org" } } : failure === "typed-error"
    ? { user: { id: "recipient", organizationId: "org" }, accountRefreshError: "ACCOUNT_REFRESH_FAILED" }
    : { user: { id: "recipient", organizationId: "old-org" } });
  render(<RegisterPage />);
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  fireEvent.click(await screen.findByRole("button", { name: "Accept invitation and join team" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/session/i);
  expect(screen.queryByText(/Invitation accepted/)).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Continue to team" })).not.toBeInTheDocument();
});

it("retries only session synchronization after enrollment has committed", async () => {
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ organization_id: "org", name: "Test Lab", role: "member" }) });
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: "accepted" }) });
  update.mockResolvedValueOnce(null);
  render(<RegisterPage />);
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  fireEvent.click(await screen.findByRole("button", { name: "Accept invitation and join team" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/session/i);
  fireEvent.click(screen.getByRole("button", { name: "Retry session refresh" }));
  expect(await screen.findByText(/Invitation accepted/)).toBeInTheDocument();
  expect(apiFetch).toHaveBeenCalledTimes(2);
  expect(update).toHaveBeenCalledTimes(2);
});

it("does not offer acceptance after a failed review", async () => {
  apiFetch.mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "Invalid or unavailable invitation" }) });
  render(<RegisterPage />);
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid or unavailable invitation");
  expect(screen.queryByRole("button", { name: "Accept invitation and join team" })).not.toBeInTheDocument();
  expect(apiFetch).toHaveBeenCalledTimes(1);
});

it.each(["Verify your email before accepting an invitation", "Invitation email does not match your account"])("shows acceptance errors without claiming success (%s)", async (detail) => {
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ organization_id: "org", name: "Test Lab", role: "member" }) });
  apiFetch.mockResolvedValueOnce({ ok: false, json: async () => ({ detail }) });
  render(<RegisterPage />);
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  fireEvent.click(await screen.findByRole("button", { name: "Accept invitation and join team" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  expect(screen.queryByText(/Invitation accepted/)).not.toBeInTheDocument();
  expect(update).not.toHaveBeenCalled();
});

it("keeps registration available and requires sign-in before invitation review", () => {
  session.status = "unauthenticated";
  render(<RegisterPage />);
  expect(screen.getByRole("button", { name: "Create Account" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Review invitation" })).not.toBeInTheDocument();
  expect(apiFetch).not.toHaveBeenCalled();
});
