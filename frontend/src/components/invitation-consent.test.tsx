import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import RegisterPage from "@/app/(auth)/register/page";

const { apiFetch, signIn, session } = vi.hoisted(() => ({ apiFetch: vi.fn(), signIn: vi.fn(), session: { status: "authenticated" } }));
vi.mock("@/lib/api", () => ({ apiFetch, backendUrl: (path: string) => path }));
vi.mock("next-auth/react", () => ({ signIn, useSession: () => session }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("invite=recipient-token") }));

beforeEach(() => { vi.clearAllMocks(); session.status = "authenticated"; });

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
  expect(apiFetch).toHaveBeenLastCalledWith("/api/organizations/org/invites/accept", expect.objectContaining({
    method: "POST", body: JSON.stringify({ token: "recipient-token" }),
  }));
});

it("does not offer acceptance after a failed review", async () => {
  apiFetch.mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "Invalid or unavailable invitation" }) });
  render(<RegisterPage />);
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid or unavailable invitation");
  expect(screen.queryByRole("button", { name: "Accept invitation and join team" })).not.toBeInTheDocument();
  expect(apiFetch).toHaveBeenCalledTimes(1);
});

it("shows verification errors without claiming success", async () => {
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ organization_id: "org", name: "Test Lab", role: "member" }) });
  apiFetch.mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "Verify your email before accepting an invitation" }) });
  render(<RegisterPage />);
  fireEvent.click(screen.getByRole("button", { name: "Review invitation" }));
  fireEvent.click(await screen.findByRole("button", { name: "Accept invitation and join team" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Verify your email");
  expect(screen.queryByText(/Invitation accepted/)).not.toBeInTheDocument();
});

it("keeps registration available and requires sign-in before invitation review", () => {
  session.status = "unauthenticated";
  render(<RegisterPage />);
  expect(screen.getByRole("button", { name: "Create Account" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Review invitation" })).not.toBeInTheDocument();
  expect(apiFetch).not.toHaveBeenCalled();
});
