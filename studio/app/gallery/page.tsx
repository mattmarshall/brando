import Link from "next/link";
import { headers } from "next/headers";

import { sessionFor } from "@/lib/auth";
import { AccountControl, SignIn } from "@/app/_components/studio-auth";
import { catalogConfigured, listBrands } from "@/lib/catalog";

/**
 * Every brand the studio has made — the live replacement for `//console`.
 *
 * A server component, because the catalog is a database read and there is
 * nothing interactive on this page. The cards render the palette rather than
 * the mark: a mark means a service round trip each, and a wall of them would
 * make the gallery slower than the thing it indexes. The colours are already in
 * the spec.
 */
export const dynamic = "force-dynamic";

export default async function GalleryPage() {
  const isDev = process.env.NODE_ENV === "development";
  const session = isDev ? undefined : await sessionFor(await headers());
  if (!isDev && !session) return <SignIn />;

  const brands = catalogConfigured() ? await listBrands() : [];

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-4 lg:px-8">
        <Link className="font-medium text-sm tracking-tight" href="/">
          brando studio
        </Link>
        <nav className="flex items-center gap-4">
          <span className="text-sm">Catalog</span>
          <Link className="text-muted-foreground text-sm hover:text-foreground" href="/">
            New brief
          </Link>
          {session ? (
            <AccountControl
              email={session.user.email}
              image={session.user.image}
              name={session.user.name}
            />
          ) : null}
        </nav>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 lg:px-8">
        <h1 className="font-medium text-3xl tracking-tighter">Catalog</h1>
        <p className="mt-1 text-muted-foreground">
          {catalogConfigured()
            ? `${brands.length} brand${brands.length === 1 ? "" : "s"}.`
            : "This studio has no catalog database, so nothing is kept between runs. Set DATABASE_URL to keep brands."}
        </p>

        {brands.length === 0 ? null : (
          <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {brands.map((entry) => (
              <li key={entry.id}>
                <Link
                  className="flex flex-col gap-3 rounded-lg border p-4 transition-colors hover:border-foreground/40"
                  href={`/b/${encodeURIComponent(entry.id)}`}
                >
                  <div className="flex h-16 overflow-hidden rounded border">
                    {(["bg", "surface", "accent", "accent_strong", "fg"] as const).map((role) => (
                      <span
                        className="flex-1"
                        key={role}
                        style={{ background: entry.spec.theme.light[role] }}
                      />
                    ))}
                  </div>
                  <div>
                    <p className="font-medium">{entry.displayName}</p>
                    <p className="mt-0.5 text-muted-foreground text-sm">{entry.tagline}</p>
                  </div>
                  <p className="font-mono text-[11px] text-muted-foreground">
                    {entry.id} · {entry.createdAt.slice(0, 10)}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
