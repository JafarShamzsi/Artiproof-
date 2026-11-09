import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import SettingsPage from "./page";
import { apiFetch } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams() }));
vi.mock("next-auth/react", () => ({ useSession: () => ({ data: null, status: "unauthenticated" }), signOut: vi.fn() }));
vi.mock("@/contexts/ColorModeContext", () => ({ useColorMode: () => ({ mode: "light", setMode: vi.fn() }) }));
vi.mock("@/contexts/ThemeContext", () => ({ useTheme: () => ({ highContrast: false, toggleHighContrast: vi.fn() }) }));
vi.mock("@/contexts/TourContext", () => ({ useTour: () => ({ startTour: vi.fn(), isCompleted: () => false, resetTour: vi.fn() }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it.each([false, true, undefined])("renders server TOTP enrollment eligibility (%s) rather than allowing Google-only lockout", async (available) => {
  vi.mocked(apiFetch).mockImplementation(async (path) => ({
    ok: path === "/api/auth/me/2fa", status: path === "/api/auth/me/2fa" ? 200 : 503,
    json: async () => ({ enabled: false, backup_codes_remaining: 0, enrollment_available: available,
      enrollment_unavailable_reason: available ? null : "Google-only TOTP completion and recovery are not supported." }),
  }) as Response);
  render(<SettingsPage />);
  const button = await screen.findByRole("button", { name: "Enable 2FA" });
  if (available) expect(button).toBeEnabled();
  else {
    expect(button).toBeDisabled();
    expect(screen.getByText("Google-only TOTP completion and recovery are not supported.")).toBeVisible();
  }
});
