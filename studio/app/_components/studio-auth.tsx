"use client";

/**
 * Sign in, and the account menu. GitHub, because that is who this studio is for.
 *
 * Adapted from eve's own web template, which ships the same two components
 * against Vercel as the provider. Keeping the shape means the auth surface
 * looks like every other eve app rather than like something invented here.
 */
import { LogOutIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { authClient } from "@/lib/auth-client";

export function SignIn() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string>();

  async function signIn() {
    setPending(true);
    setError(undefined);
    try {
      const result = await authClient.signIn.social({ callbackURL: "/", provider: "github" });
      if (!result.error) return;
      setPending(false);
      setError(result.error.message ?? "GitHub declined the sign-in.");
    } catch (cause) {
      setPending(false);
      setError(cause instanceof Error ? cause.message : "Could not reach GitHub.");
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-6 text-foreground">
      <section className="flex w-full max-w-sm flex-col items-center text-center">
        <h1 className="font-medium text-4xl tracking-tighter">brando studio</h1>
        <p className="mt-2 text-muted-foreground text-sm">
          A brand agency of nine agents over one deterministic tier. Sign in to brief it.
        </p>
        <Button className="mt-6 w-full gap-2" disabled={pending} onClick={signIn}>
          <GitHubMark className="size-4" />
          {pending ? "Redirecting…" : "Continue with GitHub"}
        </Button>
        {error ? (
          <p className="mt-3 text-destructive text-sm" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    </main>
  );
}

export function AccountControl({
  email,
  image,
  name,
}: {
  readonly email: string;
  readonly image?: string | null;
  readonly name: string;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [pending, setPending] = useState(false);

  async function signOut() {
    setPending(true);
    try {
      await authClient.signOut({
        fetchOptions: {
          onError: () => setPending(false),
          onSuccess: () => window.location.assign("/"),
        },
      });
    } catch {
      setPending(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          aria-label={`Open account menu for ${name}`}
          className="relative size-7 cursor-pointer overflow-hidden rounded-full p-0"
          size="icon-sm"
          variant="ghost"
        >
          {image && !imageFailed ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              alt=""
              className="size-full object-cover"
              onError={() => setImageFailed(true)}
              src={image}
            />
          ) : (
            <span aria-hidden className="font-medium text-xs">
              {initials(name, email)}
            </span>
          )}
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-full border border-black/20 dark:border-white/25"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <div className="min-w-0 px-2 py-1.5 text-sm">
          <span className="block truncate font-medium leading-5" title={name}>
            {name}
          </span>
          <span className="block truncate text-muted-foreground leading-5" title={email}>
            {email}
          </span>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="cursor-pointer justify-between" disabled={pending} onSelect={signOut}>
          {pending ? "Logging out…" : "Log out"}
          <LogOutIcon aria-hidden />
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function initials(name: string, email: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0]?.[0] ?? ""}${parts.at(-1)?.[0] ?? ""}`.toUpperCase();
  return (parts[0]?.[0] ?? email[0] ?? "?").toUpperCase();
}

function GitHubMark({ className }: { readonly className?: string }) {
  return (
    <svg aria-hidden className={className} fill="currentColor" viewBox="0 0 16 16">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}
