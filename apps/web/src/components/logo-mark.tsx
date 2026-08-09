import type { SVGProps } from "react";

import { cn } from "@/lib/utils";

export type LogoMarkProps = Omit<SVGProps<SVGSVGElement>, "children">;

export const LOGO_MARK_VIEW_BOX = "4.65 3.25 24 27";
export const LOGO_MARK_LAYERS = [
  {
    d: "M8.15 25.8V14.15c0-4.1 3.33-7.43 7.43-7.43h9.37a3.98 3.98 0 0 1-3.98 3.98h-5.52c-3.2 0-5.5 2.05-6.2 5-.2.85-.3 1.65-.3 2.55v2.4c0 2 1.25 3.5 3.1 3.65-1.9.1-3.35.65-3.9 1.5Z",
    opacity: 0.2,
  },
  {
    d: "M8.15 16.85v-3.4a7.12 7.12 0 0 1 7.12-7.12h9.88a4.2 4.2 0 0 1-4.2 4.2h-5.67a6.37 6.37 0 0 0-6.06 4.27c-.4 1.12-.87 1.82-1.07 2.05Z",
    opacity: 0.5,
  },
  {
    d: "M8.15 25.8v-7.08a7.2 7.2 0 0 1 6.95-5.67h6.82a4.2 4.2 0 0 1-4.2 4.2h-2.9a2.67 2.67 0 0 0-2.67 2.67v1.1c0 2.65-1.8 4.78-4 4.78Z",
    opacity: 0.9,
  },
] as const;

/**
 * Final finance logo mark based on design variant 21.
 * It uses `currentColor`, so the surrounding context controls its accent.
 */
export function LogoMark({ className, ...props }: LogoMarkProps) {
  return (
    <svg
      {...props}
      viewBox={LOGO_MARK_VIEW_BOX}
      fill="none"
      aria-hidden="true"
      focusable="false"
      shapeRendering="geometricPrecision"
      className={cn("h-8 w-8 shrink-0", className)}
    >
      {LOGO_MARK_LAYERS.map((layer) => (
        <path
          key={layer.d}
          d={layer.d}
          fill="currentColor"
          opacity={layer.opacity}
        />
      ))}
    </svg>
  );
}

/*
Archived design references — intentionally not rendered.

Variant 17:
  viewBox="0 0 32 32"
  shared: M26.97 3.97 12.56 3.9l-1.57.38-1.61.72-2.22 1.79-1.61 2.44-.69 2.41.14 6.68-.21 1.73-.03 7.02.27 1 1.03.14 1.64-.42 1.1-.72.72-.83.68-1.72.14-3.92.85-1.35 1.27-.51h5.51l1.67-.38 1.2-.72.89-.93.89-2.14v-1.17l-.62-.41-9.51.03-2.63.62-2.84 1.69-.58-1.59.82-1.27 1.2-1.14 1.26-.82 2.43-.83 10.3-.1 1.74-.42 1.27-.79 1.1-1.34.58-1.65.03-.97Z (18%)
  upper:  m26.83 4.24-13.79-.03-1.64.31-1.68.69-2.22 1.72-1.64 2.37-.72 2.55v4l1.57-3.21 1.34-1.37 1.53-1.04 1.48-.62 1.81-.34 9.61.03 1.34-.27 1.3-.73 1.09-1.2.62-1.55Z (62%)
  lower:  m22.35 13.47-.31-.21-10.03.11-2.6.79-2.46 1.65-1.23 1.76-.62 1.86.04 8.43.82.14 1.44-.31 1.06-.62.78-.83.72-1.65.17-4.13.96-1.45 1.16-.51h5.44l1.95-.42 1.3-.86.96-1.27.45-1.28Z (92%)

Variant 20:
  viewBox="4.65 3.25 24 27"
  bridge: M8.15 25.8V14.2c0-4.1 3.33-7.43 7.43-7.43h2.65c-4.1 1.38-6.88 4.93-6.88 9.03v4.45c0 2.5-1.2 4.55-3.2 5.55Z (gradient 24% → 8%)
  upper:  M8.15 16.85v-3.4a7.12 7.12 0 0 1 7.12-7.12h9.88a4.2 4.2 0 0 1-4.2 4.2h-5.67a6.37 6.37 0 0 0-6.06 4.27c-.4 1.12-.87 1.82-1.07 2.05Z (52%)
  lower:  M8.15 25.8v-7.08a7.2 7.2 0 0 1 6.95-5.67h6.82a4.2 4.2 0 0 1-4.2 4.2h-2.9a2.67 2.67 0 0 0-2.67 2.67v1.1c0 2.65-1.8 4.78-4 4.78Z (84%)
*/
