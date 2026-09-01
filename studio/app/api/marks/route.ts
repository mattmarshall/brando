/**
 * Render a finished MarkProgram, for the browser.
 *
 * WHY THE UI RENDERS THE MARK AND THE AGENT DOES NOT SEE IT. `render_mark` — the
 * tool the mark designer calls — deliberately returns filenames, sizes and the
 * colours the fills resolved to, not the SVG. A few kilobytes of path data would
 * fill the model's context with coordinates it did not choose and cannot check:
 * it chose parameters and relations, and the interpreter computed the geometry.
 *
 * The browser has the opposite need. So this is the same call, made again, for a
 * different reader — the one that can actually look at it.
 */
import { create } from "@bufbuild/protobuf";
import { NextResponse } from "next/server";

import { markProgramSchema, themeSchema } from "@/agent/lib/brand";
import { brando } from "@/agent/lib/brando/client";
import { RenderMarkRequestSchema } from "@/agent/lib/brando/gen/brando/v1/brand_service_pb";
import { toMarkProgramMessage } from "@/agent/lib/proto-json";
import { toThemeMessage } from "@/agent/lib/theme-message";
import { signedIn } from "@/lib/auth";
import { z } from "zod";

// Node, not edge: the client dials the deterministic tier over HTTP with the
// generated Connect stubs, which are not edge-compatible.
export const runtime = "nodejs";

const bodySchema = z.object({
  program: markProgramSchema,
  theme: themeSchema,
  variants: z.array(z.string().min(1)).optional(),
});

export async function POST(request: Request) {
  if (!(await signedIn(request.headers))) {
    return NextResponse.json({ error: "sign in first" }, { status: 401 });
  }

  let input: z.infer<typeof bodySchema>;
  try {
    input = bodySchema.parse(await request.json());
  } catch (cause) {
    // The caller here is our own page, so a failure means the brand the agency
    // produced does not match the contract it was supposed to produce — worth
    // saying precisely rather than rendering an empty box.
    return NextResponse.json(
      { error: cause instanceof Error ? cause.message : "malformed mark" },
      { status: 400 },
    );
  }

  try {
    const { render } = brando();
    const response = await render.renderMark(
      create(RenderMarkRequestSchema, {
        program: toMarkProgramMessage(input.program),
        theme: toThemeMessage(input.theme),
        variants: input.variants ?? [],
      }),
    );

    const decoder = new TextDecoder();
    return NextResponse.json({
      files: response.files.map((file) => ({
        name: file.name,
        // The SVG itself, as text. These are a few kilobytes each and the page
        // inlines them, so the mark is part of the document rather than a
        // request the browser has to make and a URL something has to serve.
        svg: decoder.decode(file.content),
      })),
    });
  } catch (cause) {
    return NextResponse.json(
      { error: cause instanceof Error ? cause.message : "the mark did not render" },
      { status: 502 },
    );
  }
}
