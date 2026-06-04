import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center border border-basin bg-basin/10 px-2 py-1 text-xs font-bold uppercase text-basin", className)} {...props} />;
}
