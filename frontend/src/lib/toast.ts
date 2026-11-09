/**
 * Thin wrapper over sonner so call sites import from one place and we
 * can centralize defaults (durations, descriptions) without retrofitting
 * later. Keep the surface tiny — most uses are .success() / .error().
 */

import { toast as sonnerToast, type ExternalToast } from "sonner";

export const toast = {
  success(message: string, options?: ExternalToast) {
    return sonnerToast.success(message, options);
  },
  error(message: string, options?: ExternalToast) {
    // Errors stay on screen 1.5x longer than the default — they're more
    // important than success acknowledgements and the user may need to read
    // a description.
    return sonnerToast.error(message, { duration: 6000, ...options });
  },
  info(message: string, options?: ExternalToast) {
    return sonnerToast(message, options);
  },
  warning(message: string, options?: ExternalToast) {
    // Same elevated duration as error toasts so users see + read them.
    return sonnerToast.warning(message, { duration: 6000, ...options });
  },
  /** For long-running operations — returns a sonner id you can resolve later. */
  loading(message: string, options?: ExternalToast) {
    return sonnerToast.loading(message, options);
  },
  /** Wrap a promise: shows loading, then success/error based on outcome. */
  promise<T>(
    promise: Promise<T>,
    messages: { loading: string; success: string; error: string },
  ) {
    return sonnerToast.promise(promise, messages);
  },
  dismiss(id?: string | number) {
    return sonnerToast.dismiss(id);
  },
};
