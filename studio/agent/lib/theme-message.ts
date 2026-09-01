/**
 * The zod contract's Theme, as the proto's.
 *
 * WHY THIS IS ITS OWN MODULE. Two callers need it and they sit on opposite
 * sides of the app: the tools the specialists call (`agent/lib/brand-tools.ts`)
 * and the route the browser calls to render a finished mark
 * (`app/api/marks/route.ts`). One conversion, or the palette a colorist chose
 * and the palette a mark renders against can silently differ — which is the
 * exact class of drift brando exists to remove.
 *
 * The palette keys are snake_case in `brand.ts` on purpose: those strings are
 * the ROLE VOCABULARY — the same names `marklib.palette`'s gate table uses and
 * the same ones a MarkProgram's `ThemeColor.role` names — so spelling them
 * camelCase in one place and snake_case in another would mean a specialist had
 * to know which context it was in. protobuf-es wants camelCase, and this
 * function is the single place that knows.
 */
import { create } from "@bufbuild/protobuf";

import type { Theme } from "./brand";
import { PaletteSchema, ThemeSchema, TypographySchema } from "./brando/gen/proto/theme_pb";

export function toThemeMessage(theme: Theme) {
  const palette = (p: Theme["light"]) =>
    create(PaletteSchema, {
      bg: p.bg, surface: p.surface, fg: p.fg, muted: p.muted, border: p.border,
      accent: p.accent, accentStrong: p.accent_strong, onAccent: p.on_accent,
      danger: p.danger, success: p.success, codeBg: p.code_bg, codeFg: p.code_fg,
      warning: p.warning, info: p.info,
    });
  return create(ThemeSchema, {
    id: theme.id,
    displayName: theme.displayName,
    light: palette(theme.light),
    dark: palette(theme.dark),
    typography: create(TypographySchema, {
      sans: theme.typography.sans,
      mono: theme.typography.mono,
      display: theme.typography.display ?? "",
      headingTracking: theme.typography.headingTracking,
      baseSizePx: theme.typography.baseSizePx,
      headingWeight: theme.typography.headingWeight,
      bodyWeight: theme.typography.bodyWeight,
      fonts: theme.typography.fonts.map((f) => ({
        $typeName: "meridian.theme.v1.FontSource" as const,
        family: f.family, srcUri: f.srcUri, weight: f.weight,
        style: f.style ?? "", unicodeRange: "", display: "",
      })),
    }),
    metrics: {
      $typeName: "meridian.theme.v1.Metrics" as const,
      radiusPx: theme.metrics.radiusPx,
      unitPx: theme.metrics.unitPx,
    },
  });
}
