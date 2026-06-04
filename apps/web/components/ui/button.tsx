import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type ButtonVariant = "default" | "outline" | "signal" | "ghost";

export function Button({
  className,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={cn(
        "focus-ring inline-flex h-10 items-center justify-center gap-2 border px-3 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-60",
        variant === "default" && "border-ink bg-ink text-paper hover:bg-signal",
        variant === "outline" && "border-zincLine bg-white text-ink hover:border-ink",
        variant === "signal" && "border-ink bg-citrus text-ink hover:bg-signal hover:text-white",
        variant === "ghost" && "border-transparent bg-transparent text-ink hover:border-zincLine hover:bg-white",
        className
      )}
      {...props}
    />
  );
}
