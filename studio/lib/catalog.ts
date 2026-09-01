/**
 * Every brand the studio has made.
 *
 * WHY THIS IS SO SMALL. brando already has a resource model for brands —
 * `BrandService`, `RevisionService`, the `.brando` archive — designed, linted
 * against AIP, and implemented. Reproducing revisions, artifacts and lifecycle
 * in Postgres would be inventing that twice, and the second one would be the
 * one that drifts. So this table holds exactly what a gallery needs to show a
 * card and reopen a brand: the id, the name, when it was made, and the spec the
 * agency submitted. Everything else is a question for the service.
 *
 * The spec is JSONB rather than columns for the same reason: its shape is
 * `brandSpecSchema`'s, checked on the way in and on the way out, and a schema
 * transcribed into DDL is a second declaration of the first.
 */
import { neon } from "@neondatabase/serverless";

import { brandSpecSchema, type BrandSpec } from "@/agent/lib/brand";

export type CatalogEntry = {
  readonly id: string;
  readonly displayName: string;
  readonly tagline: string;
  readonly createdAt: string;
  readonly spec: BrandSpec;
};

/**
 * Whether there is a catalog at all.
 *
 * A studio with no database still works — the agency runs, the brand renders,
 * the run is a URL you can share. Only the gallery needs storage. So a missing
 * `DATABASE_URL` makes the gallery say what is missing, rather than making the
 * app fail to start; an app that refuses to boot over an optional feature is a
 * worse failure than the feature being absent.
 */
export function catalogConfigured(): boolean {
  return Boolean(process.env.DATABASE_URL?.trim());
}

function sql() {
  const url = process.env.DATABASE_URL?.trim();
  if (!url) {
    throw new Error(
      "DATABASE_URL is not set, so there is no catalog. The studio itself does not need one: " +
        "run a brief and the brand renders from the session.",
    );
  }
  return neon(url);
}

let ensured: Promise<void> | undefined;

/**
 * The one table, created on first use.
 *
 * A migration tool for a single table would be a dependency to keep current in
 * exchange for nothing; this is idempotent DDL and the schema is right here
 * where a reader looking for it will be.
 */
function ensure(): Promise<void> {
  ensured ??= (async () => {
    const query = sql();
    await query`
      CREATE TABLE IF NOT EXISTS brands (
        id           text PRIMARY KEY,
        display_name text        NOT NULL,
        tagline      text        NOT NULL,
        spec         jsonb       NOT NULL,
        created_at   timestamptz NOT NULL DEFAULT now(),
        updated_at   timestamptz NOT NULL DEFAULT now()
      )
    `;
  })();
  return ensured;
}

export async function listBrands(): Promise<readonly CatalogEntry[]> {
  await ensure();
  const query = sql();
  const rows = await query`
    SELECT id, display_name, tagline, spec, created_at
    FROM brands
    ORDER BY created_at DESC
    LIMIT 200
  `;
  return rows.flatMap((row) => {
    // A row whose spec no longer parses is a schema change, not a reason to
    // fail the whole gallery — so it is skipped and the rest still renders.
    const parsed = brandSpecSchema.safeParse(row.spec);
    if (!parsed.success) return [];
    return [{
      createdAt: new Date(row.created_at as string).toISOString(),
      displayName: String(row.display_name),
      id: String(row.id),
      spec: parsed.data,
      tagline: String(row.tagline),
    }];
  });
}

export async function getBrand(id: string): Promise<CatalogEntry | undefined> {
  await ensure();
  const query = sql();
  const rows = await query`
    SELECT id, display_name, tagline, spec, created_at FROM brands WHERE id = ${id}
  `;
  const row = rows[0];
  if (!row) return undefined;
  const parsed = brandSpecSchema.safeParse(row.spec);
  if (!parsed.success) return undefined;
  return {
    createdAt: new Date(row.created_at as string).toISOString(),
    displayName: String(row.display_name),
    id: String(row.id),
    spec: parsed.data,
    tagline: String(row.tagline),
  };
}

/**
 * Keep a brand.
 *
 * UPSERT ON THE BRAND ID, because the id is the archive's basename — the same
 * string `//brands/<id>` would use — and two brands with one id are not two
 * brands. Re-running a brief for `leangres` supersedes it; it does not create
 * `leangres (2)`.
 */
export async function putBrand(spec: BrandSpec): Promise<void> {
  await ensure();
  const query = sql();
  await query`
    INSERT INTO brands (id, display_name, tagline, spec)
    VALUES (${spec.id}, ${spec.displayName}, ${spec.identity.tagline}, ${JSON.stringify(spec)}::jsonb)
    ON CONFLICT (id) DO UPDATE SET
      display_name = EXCLUDED.display_name,
      tagline      = EXCLUDED.tagline,
      spec         = EXCLUDED.spec,
      updated_at   = now()
  `;
}
