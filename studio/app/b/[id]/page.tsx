import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { sessionFor } from "@/lib/auth";
import { BrandView } from "@/app/_components/brand-view";
import { AccountControl, SignIn } from "@/app/_components/studio-auth";
import { catalogConfigured, getBrand } from "@/lib/catalog";

/**
 * One kept brand, rendered by exactly the component the live run renders.
 *
 * The same `BrandView`, deliberately: a "saved brand" page that drew its own
 * swatches would be a second account of what a brand looks like, and the two
 * would diverge on the first change to either. The only difference is that
 * nothing here offers to save — it is already saved.
 */
export const dynamic = "force-dynamic";

export default async function BrandPage({
  params,
}: {
  readonly params: Promise<{ readonly id: string }>;
}) {
  const isDev = process.env.NODE_ENV === "development";
  const session = isDev ? undefined : await sessionFor(await headers());
  if (!isDev && !session) return <SignIn />;

  if (!catalogConfigured()) notFound();
  const { id } = await params;
  const entry = await getBrand(id);
  if (!entry) notFound();

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-4 lg:px-8">
        <Link className="font-medium text-sm tracking-tight" href="/">
          brando studio
        </Link>
        <nav className="flex items-center gap-4">
          <Link className="text-muted-foreground text-sm hover:text-foreground" href="/gallery">
            Catalog
          </Link>
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
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 lg:px-8">
        <BrandView spec={entry.spec} />
      </main>
    </div>
  );
}
