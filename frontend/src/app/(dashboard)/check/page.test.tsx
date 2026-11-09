import { Component, StrictMode, type ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import CheckSourcePage from "./page";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn(), backendUrl: (s: string) => s }));
vi.mock("@/lib/toast", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const quota = { detail: {
  error: "quota_exceeded", kind: "source_checks", tier: "free", used: 10,
  limit: 10, requested: 1, remaining: 0, upgrade_url: "https://untrusted.invalid/pricing",
  message: "You've used 10 of 10 source checks this month on the free tier. Upgrade to continue.",
} };
const draft = "Synthetic article text for submission testing only. ".repeat(2);
const response = (body: unknown, status = 200) => ({
  ok: status < 400, status, json: async () => body,
}) as Response;
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}
class FakeEventSource {
  static CLOSED = 2;
  static instances: FakeEventSource[] = [];
  readyState = 1;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn(() => { this.readyState = 2; });
  constructor(public url: string) { FakeEventSource.instances.push(this); }
}
const posts = () => vi.mocked(apiFetch).mock.calls.filter(([, options]) => options?.method === "POST")
  .filter(([path]) => !String(path).includes("stream-ticket"));
const submitText = async () => {
  await userEvent.click(screen.getByRole("tab", { name: "Paste Text" }));
  fireEvent.change(screen.getByPlaceholderText("Paste the article text here..."), { target: { value: draft } });
  fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
};
const savedLink = () => screen.getByRole("link", { name: /Open saved check/i });

class CrashBoundary extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false };
  static getDerivedStateFromError() { return { crashed: true }; }
  render() { return this.state.crashed ? <p>React rendering crashed</p> : this.props.children; }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.mocked(apiFetch).mockReset();
  vi.mocked(apiFetch).mockImplementation(async (path) => {
    if (String(path).includes("?")) return response({ items: [], total: 0 });
    return response(quota, 402);
  });
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("submission error rendering", () => {
  it("renders the real structured 402 message without crashing and keeps the draft", async () => {
    const user = userEvent.setup();
    render(<CrashBoundary><CheckSourcePage /></CrashBoundary>);
    await user.click(screen.getByRole("tab", { name: "Paste Text" }));
    fireEvent.change(screen.getByPlaceholderText("Paste the article text here..."), { target: { value: draft } });
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    await waitFor(() => expect(screen.queryByText("React rendering crashed")).not.toBeInTheDocument());
    expect(await screen.findByRole("alert")).toHaveTextContent(quota.detail.message);
    expect(screen.getByPlaceholderText("Paste the article text here...")).toHaveValue(draft);
    expect(screen.queryByRole("link", { name: /upgrade/i })).not.toBeInTheDocument();
  });

  const failures = [
    ["402", response(quota, 402), quota.detail.message],
    ["422", response({ detail: [{ msg: "Invalid article", input: { private: "not for display" } }] }, 422), "Invalid article"],
    ["413", response({ detail: "Request too large" }, 413), "Request too large"],
    ["429", response({ detail: "Rate limit reached" }, 429), "Rate limit reached"],
    ["500", response({ detail: { unexpected: "private payload" } }, 500), /HTTP 500/],
    ["non-JSON", { ...response(null, 502), json: async () => { throw new SyntaxError("raw HTML private payload"); } } as Response, /HTTP 502/],
    ["offline", null, /check.*history.*before/i],
  ] as const;
  describe.each(["text", "url", "document", "bulk"] as const)("%s errors", (mode) => {
    it.each(failures)("handles %s as text, keeps draft, and never retries automatically", async (_, failure, expected) => {
      vi.mocked(apiFetch).mockImplementation(async (path) => {
        if (String(path).includes("?")) return response({ items: [], total: 0 });
        if (!failure) throw new TypeError("private transport diagnostics");
        return failure;
      });
      const { container } = render(<CrashBoundary><CheckSourcePage /></CrashBoundary>);
      const tab = { text: "Paste Text", url: "Paste URL", document: "Upload PDF", bulk: "Bulk" }[mode];
      await userEvent.click(screen.getByRole("tab", { name: tab }));
      if (mode === "document") {
        const file = new File(["%PDF-" + "x".repeat(100)], "draft.pdf");
        fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
      } else {
        const placeholder = mode === "url" ? "https://example.com/article..." : mode === "text" ? "Paste the article text here..." : /https:\/\/example.com\/article-1/;
        fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value: mode === "url" ? "https://example.com/synthetic" : draft } });
      }
      fireEvent.click(screen.getByRole("button", { name: mode === "bulk" ? "Run batch" : "Analyze" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(expected);
      expect(screen.queryByText("React rendering crashed")).not.toBeInTheDocument();
      expect(screen.queryByText(/private payload|transport diagnostics|raw HTML|\[object Object\]/)).not.toBeInTheDocument();
      if (mode === "document") expect(screen.getByText("draft.pdf")).toBeInTheDocument();
      else expect(screen.getByRole("textbox", { name: mode === "text" ? "Article text" : mode === "url" ? "Article URL" : "URLs or text, one item per line" })).toHaveValue(mode === "url" ? "https://example.com/synthetic" : draft);
      expect(posts()).toHaveLength(1);
      expect(useRouter().push).not.toHaveBeenCalled();
      if (mode === "bulk") expect(toast.error).toHaveBeenCalledWith(expect.any(String));
    });
  });
});

describe("text-first validation and drafts", () => {
  it("defaults to labeled text with honest minimum and bibliography limitations", async () => {
    render(<CheckSourcePage />);
    expect(screen.getByRole("tab", { name: "Paste Text" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Article text")).toHaveAccessibleDescription(/50.*trimmed.*bibliography.*unsupported/i);
    await screen.findByText("No source checks yet");
  });

  it.each(["", " ", "x".repeat(49), "x".repeat(48) + "😀", "\u001c" + "x".repeat(49) + "\u001f"])("does not POST short text %j", async (text) => {
    render(<CheckSourcePage />);
    await userEvent.click(screen.getByRole("tab", { name: "Paste Text" }));
    fireEvent.change(screen.getByPlaceholderText("Paste the article text here..."), { target: { value: text } });
    expect(screen.getByRole("button", { name: "Analyze" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    expect(posts()).toHaveLength(0);
  });

  it.each(["x".repeat(50), "x".repeat(49) + "😀", "😀".repeat(50)])("POSTs valid codepoint-length text once %j", async (text) => {
    render(<CheckSourcePage />);
    await userEvent.click(screen.getByRole("tab", { name: "Paste Text" }));
    fireEvent.change(screen.getByPlaceholderText("Paste the article text here..."), { target: { value: `  ${text}  ` } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await screen.findByRole("alert");
    expect(posts()).toHaveLength(1);
    expect(JSON.parse(posts()[0][1]!.body as string)).toEqual({ input_type: "text", input_content: text });
  });

  it.each([
    ["non-PDF", "bad.txt", 100, /only PDF/i],
    ["oversized", "large.pdf", 50 * 1024 * 1024 + 1, /too large/i],
    ["undersized", "small.pdf", 99, /too small/i],
  ])("rejects %s locally but keeps the selected filename", async (_, name, size, message) => {
    const { container } = render(<CheckSourcePage />);
    await userEvent.click(screen.getByRole("tab", { name: "Upload PDF" }));
    const file = new File(["%PDF- synthetic"], name);
    Object.defineProperty(file, "size", { value: size });
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByText(name)).toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });

  it.each([100, 50 * 1024 * 1024])("accepts .PDF with empty browser MIME at %i bytes", async (size) => {
    const { container } = render(<CheckSourcePage />);
    await userEvent.click(screen.getByRole("tab", { name: "Upload PDF" }));
    const file = new File(["%PDF-"], "synthetic.PDF", { type: "" });
    Object.defineProperty(file, "size", { value: size });
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await screen.findByRole("alert");
    expect(posts()[0][0]).toBe("/api/source-check/upload");
    expect((posts()[0][1]!.body as FormData).get("file")).toBe(file);
    expect(screen.getByText("synthetic.PDF")).toBeInTheDocument();
  });

  it("preserves separate rejected text and URL drafts when switching modes", async () => {
    render(<CheckSourcePage />);
    await submitText();
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("tab", { name: "Paste URL" }));
    const url = screen.getByLabelText("Article URL");
    expect(url).toHaveValue("");
    fireEvent.change(url, { target: { value: "https://example.com/synthetic" } });
    await userEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("tab", { name: "Paste Text" }));
    expect(screen.getByLabelText("Article text")).toHaveValue(draft);
    await userEvent.click(screen.getByRole("tab", { name: "Paste URL" }));
    expect(screen.getByLabelText("Article URL")).toHaveValue("https://example.com/synthetic");
  });
});

describe("accepted check recovery and request fencing", () => {
  function accepted(ticket: Promise<Response> | "offline" = Promise.resolve(response({ ticket: "synthetic-ticket" }))) {
    vi.mocked(apiFetch).mockImplementation(async (path) => {
      if (String(path).includes("?")) return response({ items: [], total: 0 });
      if (String(path).includes("stream-ticket")) {
        if (ticket === "offline") throw new TypeError("offline");
        return ticket;
      }
      return response({ id: "saved-check" }, 201);
    });
  }

  it("shows the actual accepted ID before a ticket or first event", async () => {
    const ticket = deferred<Response>();
    accepted(ticket.promise);
    render(<CheckSourcePage />);
    await submitText();
    expect(await screen.findByRole("link", { name: /Open saved check/i })).toHaveAttribute("href", "/check/saved-check");
    expect(screen.getByText(/saved-check/)).toBeInTheDocument();
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(screen.getByRole("button", { name: /Waiting for live progress/i })).toBeDisabled();
  });

  it.each(["text", "document"])("distinguishes %s request in flight from accepted work", async (mode) => {
    const post = deferred<Response>();
    vi.mocked(apiFetch).mockImplementation(async (path) => String(path).includes("?") ? response({ items: [], total: 0 }) : post.promise);
    const { container } = render(<CheckSourcePage />);
    if (mode === "document") {
      await userEvent.click(screen.getByRole("tab", { name: "Upload PDF" }));
      fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(["%PDF-" + "x".repeat(100)], "draft.pdf")] } });
      fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    } else await submitText();
    expect(screen.getByRole("button", { name: mode === "document" ? "Uploading..." : "Submitting..." })).toBeDisabled();
    expect(screen.queryByRole("link", { name: /Open saved check/i })).not.toBeInTheDocument();
    await act(async () => { post.resolve(response(quota, 402)); });
    expect(posts()).toHaveLength(1);
  });

  it("treats an unreadable successful POST response as acceptance unknown, never fabricated success", async () => {
    vi.mocked(apiFetch).mockImplementation(async (path) => String(path).includes("?") ? response({ items: [], total: 0 }) : {
      ...response(null, 201), json: async () => { throw new SyntaxError("private response"); },
    } as Response);
    render(<CheckSourcePage />);
    await submitText();
    expect(await screen.findByRole("alert")).toHaveTextContent(/check.*history.*before/i);
    expect(screen.queryByRole("link", { name: /Open saved check/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Article text")).toHaveValue(draft);
    expect(posts()).toHaveLength(1);
    expect(useRouter().push).not.toHaveBeenCalled();
  });

  it("accepts non-UUID IDs and safely encodes a valid Unicode path segment", async () => {
    vi.mocked(apiFetch).mockImplementation(async (path) => {
      if (String(path).includes("?")) return response({ items: [], total: 0 });
      if (String(path).includes("stream-ticket")) return response(null, 503);
      return response({ id: "saved-é:1" }, 201);
    });
    render(<CheckSourcePage />);
    await submitText();
    await waitFor(() => expect(useRouter().push).toHaveBeenCalledWith("/check/saved-%C3%A9%3A1"));
    expect(savedLink()).toHaveAttribute("href", "/check/saved-%C3%A9%3A1");
  });

  it("recovers the accepted ID when EventSource construction fails", async () => {
    accepted();
    vi.stubGlobal("EventSource", class { constructor() { throw new Error("unavailable"); } });
    render(<CheckSourcePage />);
    await submitText();
    await waitFor(() => expect(useRouter().push).toHaveBeenCalledWith("/check/saved-check"));
    expect(savedLink()).toHaveAttribute("href", "/check/saved-check");
    expect(posts()).toHaveLength(1);
  });

  it.each(["failed", "completed", "disconnect", "EOF", "malformed"])("recovers the same ID for %s without resubmitting", async (event) => {
    accepted();
    render(<CheckSourcePage />);
    await submitText();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const stream = FakeEventSource.instances[0];
    await act(async () => {
      if (event === "disconnect" || event === "EOF") {
        stream.readyState = event === "EOF" ? 2 : 0;
        stream.onerror?.();
      } else stream.onmessage?.({ data: event === "malformed" ? "not JSON" : JSON.stringify({ status: event, progress: 1, detail: "Synthetic terminal" }) });
    });
    expect(savedLink()).toHaveAttribute("href", "/check/saved-check");
    expect(posts()).toHaveLength(1);
    if (event !== "malformed") {
      expect(useRouter().push).toHaveBeenCalledWith("/check/saved-check");
      expect(stream.close).toHaveBeenCalled();
    } else expect(useRouter().push).not.toHaveBeenCalled();
    expect(JSON.stringify(vi.mocked(toast.error).mock.calls)).not.toMatch(/still running/i);
  });

  it.each([503, "offline", "bad-ticket"])("keeps accepted link and recovery on ticket %s", async (failure) => {
    accepted(failure === "offline" ? "offline" : Promise.resolve(response(failure === "bad-ticket" ? {} : null, failure === 503 ? 503 : 200)));
    render(<CheckSourcePage />);
    await submitText();
    await waitFor(() => expect(useRouter().push).toHaveBeenCalledWith("/check/saved-check"));
    expect(savedLink()).toHaveAttribute("href", "/check/saved-check");
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(posts()).toHaveLength(1);
  });

  it.each([true, false])("does not open or navigate for late ticket after unmount (ok=%s)", async (ok) => {
    const ticket = deferred<Response>();
    accepted(ticket.promise);
    const view = render(<StrictMode><CheckSourcePage /></StrictMode>);
    await submitText();
    await screen.findByRole("link", { name: /Open saved check/i });
    view.unmount();
    await act(async () => { ticket.resolve(response({ ticket: "late" }, ok ? 200 : 503)); });
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(useRouter().push).not.toHaveBeenCalled();
  });

  it("ignores ticket JSON that finishes after unmount", async () => {
    const body = deferred<unknown>();
    accepted(Promise.resolve({ ...response(null), json: () => body.promise } as Response));
    const view = render(<StrictMode><CheckSourcePage /></StrictMode>);
    await submitText();
    await screen.findByRole("link", { name: /Open saved check/i });
    view.unmount();
    await act(async () => { body.resolve({ ticket: "late-body" }); });
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(useRouter().push).not.toHaveBeenCalled();
  });

  it("closes on StrictMode unmount and ignores saved stale stream callbacks", async () => {
    accepted();
    const view = render(<StrictMode><CheckSourcePage /></StrictMode>);
    await submitText();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const stream = FakeEventSource.instances[0];
    const lateMessage = stream.onmessage;
    const lateError = stream.onerror;
    view.unmount();
    act(() => {
      lateMessage?.({ data: JSON.stringify({ status: "completed", progress: 1, detail: "Late" }) });
      lateError?.();
    });
    expect(stream.close).toHaveBeenCalled();
    expect(useRouter().push).not.toHaveBeenCalled();
  });

  it("guards same-tick click/Enter/tab switching and cross-mode duplicates", async () => {
    const post = deferred<Response>();
    vi.mocked(apiFetch).mockImplementation(async (path) => String(path).includes("?") ? response({ items: [], total: 0 }) : post.promise);
    render(<CheckSourcePage />);
    await userEvent.click(screen.getByRole("tab", { name: "Paste URL" }));
    const input = screen.getByPlaceholderText("https://example.com/article...");
    fireEvent.change(input, { target: { value: "https://example.com/synthetic" } });
    const button = screen.getByRole("button", { name: "Analyze" });
    act(() => {
      fireEvent.click(button);
      fireEvent.keyDown(input, { key: "Enter" });
      fireEvent.keyDown(input, { key: "Enter" });
      fireEvent.click(button);
      fireEvent.click(screen.getByRole("tab", { name: "Bulk" }));
    });
    expect(posts()).toHaveLength(1);
    expect(screen.getByRole("tab", { name: "Paste URL" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Bulk" })).toHaveAttribute("aria-disabled", "true");
    await act(async () => { post.resolve(response(quota, 402)); });
    expect(input).toHaveValue("https://example.com/synthetic");
  });

  it("guards duplicate bulk clicks and switching back to single while submitting", async () => {
    const post = deferred<Response>();
    vi.mocked(apiFetch).mockImplementation(async (path) => String(path).includes("?") ? response({ items: [], total: 0 }) : post.promise);
    render(<CheckSourcePage />);
    await userEvent.click(screen.getByRole("tab", { name: "Bulk" }));
    fireEvent.change(screen.getByLabelText("URLs or text, one item per line"), { target: { value: draft } });
    const button = screen.getByRole("button", { name: "Run batch" });
    act(() => {
      fireEvent.click(button);
      fireEvent.click(button);
      fireEvent.click(screen.getByRole("tab", { name: "Paste Text" }));
    });
    expect(posts()).toHaveLength(1);
    expect(screen.getByRole("tab", { name: "Bulk" })).toHaveAttribute("aria-selected", "true");
    await act(async () => { post.resolve(response({ batch_id: "batch", items: [{ id: "one" }, { id: "two" }] }, 201)); });
    expect(useRouter().push).toHaveBeenCalledWith("/check/batch/batch?ids=one%2Ctwo");
  });

  it("ignores a late accepted response after unmount without starting a ticket request", async () => {
    const post = deferred<Response>();
    vi.mocked(apiFetch).mockImplementation(async (path) => String(path).includes("?") ? response({ items: [], total: 0 }) : post.promise);
    const view = render(<CheckSourcePage />);
    await submitText();
    view.unmount();
    await act(async () => { post.resolve(response({ id: "late-check" }, 201)); });
    expect(vi.mocked(apiFetch).mock.calls.some(([path]) => String(path).includes("stream-ticket"))).toBe(false);
    expect(useRouter().push).not.toHaveBeenCalled();
  });

  it("ignores callbacks from a closed prior stream during the next submission", async () => {
    accepted();
    render(<CheckSourcePage />);
    await submitText();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const first = FakeEventSource.instances[0];
    const staleMessage = first.onmessage;
    const staleError = first.onerror;
    await act(async () => { first.onerror?.(); });
    vi.mocked(useRouter().push).mockClear();
    await submitText();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    act(() => {
      staleMessage?.({ data: JSON.stringify({ status: "completed", detail: "stale", progress: 1 }) });
      staleError?.();
    });
    expect(useRouter().push).not.toHaveBeenCalled();
    expect(FakeEventSource.instances[1].close).not.toHaveBeenCalled();
    expect(posts()).toHaveLength(2);
  });

  it("ignores malformed event shapes and bounds recorded milestones", async () => {
    accepted();
    render(<CrashBoundary><CheckSourcePage /></CrashBoundary>);
    await submitText();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const stream = FakeEventSource.instances[0];
    act(() => {
      for (const body of [null, {}, { detail: {}, status: "completed", progress: 1 }, { detail: "bad", status: "processing", progress: 99 }]) {
        stream.onmessage?.({ data: JSON.stringify(body) });
      }
      for (let i = 0; i < 105; i++) stream.onmessage?.({ data: JSON.stringify({ detail: `Milestone ${i}`, status: "processing", progress: 0.5 }) });
    });
    expect(screen.queryByText("React rendering crashed")).not.toBeInTheDocument();
    expect(screen.queryByText("Milestone 0")).not.toBeInTheDocument();
    expect(screen.getAllByText("Milestone 104")).toHaveLength(2); // visible and polite live region
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(useRouter().push).not.toHaveBeenCalled();
  });

  it.each([null, "", " ", 123, "../bad", "a/b", "a?b", "a#b", "a%2fb", ".", ".."])("does not invent a result URL for invalid ID %j", async (id) => {
    vi.mocked(apiFetch).mockImplementation(async (path) => String(path).includes("?") ? response({ items: [], total: 0 }) : response({ id }, 201));
    render(<CheckSourcePage />);
    await submitText();
    expect(await screen.findByRole("alert")).toHaveTextContent(/check.*history.*before/i);
    expect(screen.queryByRole("link", { name: /Open saved check/i })).not.toBeInTheDocument();
    expect(useRouter().push).not.toHaveBeenCalled();
    expect(posts()).toHaveLength(1);
  });
});
