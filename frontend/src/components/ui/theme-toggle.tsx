"use client";

import { Sun, Moon, Monitor } from "lucide-react";

import { useColorMode } from "@/contexts/ColorModeContext";
import { cn } from "@/lib/utils";

const options = [
  { value: "light", label: "Light", icon: Sun },
  { value: "system", label: "System", icon: Monitor },
  { value: "dark", label: "Dark", icon: Moon },
] as const;

/** Three-position color-mode toggle. Renders as a segmented pill so the
 *  current state is always visible (vs a hidden cycle behind one icon).
 *  Keyboard-accessible, broadcasts state via aria-pressed per option. */
export function ThemeToggle({ className }: { className?: string }) {
  const { mode, setMode } = useColorMode();

  return (
    <div
      role="radiogroup"
      aria-label="Color mode"
      className={cn(
        "inline-flex items-center rounded-full border border-border-default bg-surface-card p-0.5",
        className,
      )}
    >
      {options.map((opt) => {
        const Icon = opt.icon;
        const isActive = mode === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            aria-label={opt.label}
            onClick={() => setMode(opt.value)}
            className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50",
              isActive
                ? "bg-brand text-white"
                : "text-fg-tertiary hover:text-fg-primary",
            )}
          >
            <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
        );
      })}
    </div>
  );
}
