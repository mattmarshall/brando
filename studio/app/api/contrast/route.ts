/**
 * The contrast matrix for a finished theme, for the browser.
 *
 * WHY THE PAGE DOES NOT COMPUTE THIS. A relative-luminance formula is fifteen
 * lines and every one of those lines is an opportunity to disagree with the
 * gate that actually decides whether a brand ships. brando's history is the
 * cost of exactly that kind of near-copy — four incompatible fit formulas, a
 * palette authored five times — so the swatch panel asks the same
 * `marklib.palette` the colorist was held to, and shows what it says.
 *
 * The colorist's own `check_contrast` results are in the transcript, but they
 * are checks of INTERMEDIATE palettes. This is the finished one.
 */
import { create } from "@bufbuild/protobuf";
import { NextResponse } from "next/server";
import { z } from "zod";

import { themeSchema } from "@/agent/lib/brand";
import { brando } from "@/agent/lib/brando/client";
import { CheckContrastRequestSchema } from "@/agent/lib/brando/gen/brando/v1/brand_service_pb";
import { toThemeMessage } from "@/agent/lib/theme-message";
import { signedIn } from "@/lib/auth";

export const runtime = "nodejs";

const bodySchema = z.object({ theme: themeSchema });

export async function POST(request: Request) {
  if (!(await signedIn(request.headers))) {
    return NextResponse.json({ error: "sign in first" }, { status: 401 });
  }

  let input: z.infer<typeof bodySchema>;
  try {
    input = bodySchema.parse(await request.json());
  } catch (cause) {
    return NextResponse.json(
      { error: cause instanceof Error ? cause.message : "malformed theme" },
      { status: 400 },
    );
  }

  try {
    const { render } = brando();
    const response = await render.checkContrast(
      create(CheckContrastRequestSchema, { theme: toThemeMessage(input.theme) }),
    );
    return NextResponse.json({
      findings: response.contrast.map((finding) => ({
        mode: finding.mode,
        foregroundRole: finding.foregroundRole,
        backgroundRole: finding.backgroundRole,
        ratio: Number(finding.ratio.toFixed(2)),
        minimum: finding.minimum,
        severity: finding.severity === 1 ? "error" : "warn",
      })),
    });
  } catch (cause) {
    return NextResponse.json(
      { error: cause instanceof Error ? cause.message : "the gate did not answer" },
      { status: 502 },
    );
  }
}
