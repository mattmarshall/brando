/**
 * The catalog, as two verbs.
 *
 * SAVING IS THE BROWSER'S CALL, not the director's. A ninth tool that wrote to
 * Postgres would give a model the ability to overwrite a brand mid-run, and the
 * run is exactly when a brand is least finished — the critic has not spoken yet.
 * The page saves what `submit_brand` returned, once, after it returned.
 */
import { NextResponse } from "next/server";

import { brandSpecSchema } from "@/agent/lib/brand";
import { signedIn } from "@/lib/auth";
import { catalogConfigured, listBrands, putBrand } from "@/lib/catalog";

export const runtime = "nodejs";

export async function GET(request: Request) {
  if (!(await signedIn(request.headers))) {
    return NextResponse.json({ error: "sign in first" }, { status: 401 });
  }
  if (!catalogConfigured()) return NextResponse.json({ brands: [], configured: false });
  return NextResponse.json({ brands: await listBrands(), configured: true });
}

export async function POST(request: Request) {
  if (!(await signedIn(request.headers))) {
    return NextResponse.json({ error: "sign in first" }, { status: 401 });
  }
  if (!catalogConfigured()) {
    return NextResponse.json(
      { error: "DATABASE_URL is not set, so this studio has no catalog to save to." },
      { status: 503 },
    );
  }

  const parsed = brandSpecSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ") },
      { status: 400 },
    );
  }

  await putBrand(parsed.data);
  return NextResponse.json({ id: parsed.data.id });
}
