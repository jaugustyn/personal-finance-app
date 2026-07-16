export type ColorTheme = "light" | "dark";

interface RgbColor {
  red: number;
  green: number;
  blue: number;
}

const THEME_SURFACE: Record<ColorTheme, RgbColor> = {
  light: { red: 255, green: 255, blue: 255 },
  dark: { red: 22, green: 28, blue: 39 },
};

const DARK_CONTRAST = "#0f172a";
const LIGHT_CONTRAST = "#f8fafc";
const MIN_ACCENT_CONTRAST = 1.35;
const MIN_CHART_CONTRAST = 2.5;

export interface CategoryAccentStyle {
  backgroundColor: string;
  innerOutline: string | undefined;
}

export interface CategoryChartStyle {
  fill: string;
  stroke: string;
  needsStroke: boolean;
}

export function getCategoryAccentStyle(
  color: string,
  theme: ColorTheme,
): CategoryAccentStyle {
  const parsed = parseHexColor(color);
  if (!parsed) {
    return { backgroundColor: color, innerOutline: undefined };
  }

  const surface = THEME_SURFACE[theme];
  const tintedSurface = composite(parsed, surface, 0.12);
  const needsOutline = contrastRatio(parsed, tintedSurface) < MIN_ACCENT_CONTRAST;

  return {
    backgroundColor: toRgba(parsed, 0.12),
    innerOutline: needsOutline
      ? relatedOutlineColor(parsed, theme)
      : undefined,
  };
}

export function getCategoryChartStyle(
  color: string,
  theme: ColorTheme,
): CategoryChartStyle {
  const parsed = parseHexColor(color);
  if (!parsed) {
    return {
      fill: color,
      stroke: `hsl(var(--foreground))`,
      needsStroke: false,
    };
  }

  const surface = THEME_SURFACE[theme];
  const contrast = contrastRatio(parsed, surface);
  if (contrast >= MIN_CHART_CONTRAST) {
    return {
      fill: color,
      stroke: getReadableForeground(color),
      needsStroke: false,
    };
  }

  const oklch = toOklch(parsed);
  const lightness = theme === "dark"
    ? Math.max(oklch.lightness, 0.72)
    : Math.min(oklch.lightness, 0.62);
  const fill = `oklch(${round(lightness)} ${round(oklch.chroma)} ${round(oklch.hue)})`;

  return {
    fill,
    stroke: theme === "dark" ? LIGHT_CONTRAST : DARK_CONTRAST,
    needsStroke: contrast < 1.5,
  };
}

export function getReadableForeground(color: string): string {
  const parsed = parseHexColor(color);
  if (!parsed) return LIGHT_CONTRAST;
  return contrastRatio(parsed, hexToRgb(DARK_CONTRAST)) >=
    contrastRatio(parsed, hexToRgb(LIGHT_CONTRAST))
    ? DARK_CONTRAST
    : LIGHT_CONTRAST;
}

function parseHexColor(color: string): RgbColor | null {
  const match = /^#([0-9a-f]{6})$/i.exec(color.trim());
  if (!match) return null;
  return hexToRgb(match[1]);
}

function hexToRgb(hex: string): RgbColor {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return {
    red: (value >> 16) & 255,
    green: (value >> 8) & 255,
    blue: value & 255,
  };
}

function composite(foreground: RgbColor, background: RgbColor, alpha: number): RgbColor {
  return {
    red: foreground.red * alpha + background.red * (1 - alpha),
    green: foreground.green * alpha + background.green * (1 - alpha),
    blue: foreground.blue * alpha + background.blue * (1 - alpha),
  };
}

function contrastRatio(left: RgbColor, right: RgbColor): number {
  const lighter = Math.max(relativeLuminance(left), relativeLuminance(right));
  const darker = Math.min(relativeLuminance(left), relativeLuminance(right));
  return (lighter + 0.05) / (darker + 0.05);
}

function relativeLuminance(color: RgbColor): number {
  const channel = (value: number) => {
    const normalized = value / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  return (
    0.2126 * channel(color.red) +
    0.7152 * channel(color.green) +
    0.0722 * channel(color.blue)
  );
}

function relatedOutlineColor(color: RgbColor, theme: ColorTheme): string {
  const oklch = toOklch(color);
  const lightness = theme === "dark"
    ? Math.max(oklch.lightness, 0.42)
    : Math.min(oklch.lightness, 0.72);
  return `oklch(${round(lightness)} ${round(oklch.chroma)} ${round(oklch.hue)})`;
}

function toRgba(color: RgbColor, alpha: number): string {
  return `rgba(${Math.round(color.red)}, ${Math.round(color.green)}, ${Math.round(color.blue)}, ${alpha})`;
}

function toOklch(color: RgbColor): {
  lightness: number;
  chroma: number;
  hue: number;
} {
  const linear = (value: number) => {
    const normalized = value / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  const red = linear(color.red);
  const green = linear(color.green);
  const blue = linear(color.blue);

  const l = Math.cbrt(0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue);
  const m = Math.cbrt(0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue);
  const s = Math.cbrt(0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue);

  const lightness = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
  const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const b = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  const chroma = Math.hypot(a, b);
  const hue = chroma < 0.0001
    ? 0
    : (Math.atan2(b, a) * 180) / Math.PI + (Math.atan2(b, a) < 0 ? 360 : 0);

  return { lightness, chroma, hue };
}

function round(value: number): string {
  return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}
