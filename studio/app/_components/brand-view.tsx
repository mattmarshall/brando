"use client";

/**
 * The finished brand, as the thing itself rather than as a transcript.
 *
 * Every number on this page came from brando. The mark is `marklib` executing
 * the MarkProgram the designer wrote; the ratios are `marklib.palette`'s gate,
 * asked again about the FINAL palette rather than read out of an intermediate
 * check in the transcript. The model chose parameters, roles and words — it did
 * not draw anything here and it did not compute anything here.
 */
import { useEffect, useState } from "react";
import { CheckIcon, DownloadIcon, TriangleAlertIcon } from "lucide-react";

import type { BrandSpec, Theme } from "@/agent/lib/brand";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ContrastFinding = {
  readonly mode: string;
  readonly foregroundRole: string;
  readonly backgroundRole: string;
  readonly ratio: number;
  readonly minimum: number;
  readonly severity: "error" | "warn";
};

type MarkFile = { readonly name: string; readonly svg: string };

const ROLES = [
  "bg", "surface", "fg", "muted", "border", "accent", "accent_strong",
  "on_accent", "danger", "success", "code_bg", "code_fg", "warning", "info",
] as const;

export function BrandView({
  spec,
  onSaved,
}: {
  readonly spec: BrandSpec;
  readonly onSaved?: (id: string) => void;
}) {
  return (
    <div className="flex flex-col gap-10">
      <BrandHeader onSaved={onSaved} spec={spec} />
      <MarkPanel spec={spec} />
      <PalettePanel theme={spec.theme} />
      <IdentityPanel spec={spec} />
      <TypographyPanel theme={spec.theme} />
      <ProductionPanel spec={spec} />
    </div>
  );
}

function BrandHeader({
  spec,
  onSaved,
}: {
  readonly spec: BrandSpec;
  readonly onSaved?: (id: string) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string>();

  const save = async () => {
    setSaving(true);
    setError(undefined);
    try {
      const response = await fetch("/api/brands", {
        body: JSON.stringify(spec),
        headers: { "content-type": "application/json" },
        method: "POST",
      });
      const body = (await response.json()) as { id?: string; error?: string };
      if (!response.ok) throw new Error(body.error ?? "the catalog refused it");
      setSaved(true);
      onSaved?.(body.id ?? spec.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "could not save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <header className="flex flex-wrap items-end justify-between gap-4 border-b pb-6">
      <div>
        <p className="font-mono text-muted-foreground text-xs">{spec.id}</p>
        <h1 className="mt-1 font-medium text-4xl tracking-tighter">{spec.displayName}</h1>
        <p className="mt-2 text-lg text-muted-foreground">{spec.identity.tagline}</p>
      </div>
      {onSaved === undefined ? null : (
        <div className="flex flex-col items-end gap-1">
          <Button disabled={saving || saved} onClick={save} type="button" variant="outline">
            {saved ? <CheckIcon className="size-4" /> : <DownloadIcon className="size-4" />}
            {saved ? "In the catalog" : saving ? "Saving…" : "Save to catalog"}
          </Button>
          {error ? <p className="max-w-xs text-right text-destructive text-xs">{error}</p> : null}
        </div>
      )}
    </header>
  );
}

/**
 * The mark, rendered by the service that owns the interpreter.
 *
 * As an `<img>` with a data URI rather than inlined markup. An inline `<svg>`
 * would be part of this document, which means anything that ever reached the
 * emitter's string output would be part of this document too; an image cannot
 * run script whatever it contains. The mark is drawn from a program a model
 * wrote, so that distinction is not theoretical.
 */
function MarkPanel({ spec }: { readonly spec: BrandSpec }) {
  const [files, setFiles] = useState<readonly MarkFile[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const response = await fetch("/api/marks", {
          body: JSON.stringify({
            program: spec.mark.program,
            theme: spec.theme,
            variants: spec.mark.variants,
          }),
          headers: { "content-type": "application/json" },
          method: "POST",
        });
        const body = (await response.json()) as { files?: MarkFile[]; error?: string };
        if (!live) return;
        if (!response.ok) throw new Error(body.error ?? "the mark did not render");
        setFiles((body.files ?? []).filter((file) => isComposite(file.name)));
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "the mark did not render");
      }
    })();
    return () => {
      live = false;
    };
  }, [spec]);

  return (
    <Section subtitle="Executed from the MarkProgram, at every variant the brand declares." title="The mark">
      {error ? <Problem text={error} /> : null}
      {files === undefined && error === undefined ? (
        <p className="text-muted-foreground text-sm">Rendering…</p>
      ) : null}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {(files ?? []).map((file) => (
          <figure className="flex flex-col gap-2" key={file.name}>
            <div
              className="flex aspect-square items-center justify-center rounded-lg border p-6"
              style={{ background: groundFor(file.name, spec.theme) }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt={`${spec.displayName} mark, ${variantOf(file.name)}`}
                className="size-full object-contain"
                src={`data:image/svg+xml;base64,${toBase64(file.svg)}`}
              />
            </div>
            <figcaption className="font-mono text-muted-foreground text-xs">{file.name}</figcaption>
          </figure>
        ))}
      </div>
    </Section>
  );
}

/**
 * The palette, with the ratios the gate actually returns.
 *
 * Swatches without ratios would be a colour picker. The whole reason brando
 * computes contrast rather than asking for it is that a plausible palette fails
 * WCAG in ways nobody sees by eye, so the failures are shown next to the
 * colours that cause them.
 */
function PalettePanel({ theme }: { readonly theme: Theme }) {
  const [findings, setFindings] = useState<readonly ContrastFinding[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const response = await fetch("/api/contrast", {
          body: JSON.stringify({ theme }),
          headers: { "content-type": "application/json" },
          method: "POST",
        });
        const body = (await response.json()) as { findings?: ContrastFinding[]; error?: string };
        if (!live) return;
        if (!response.ok) throw new Error(body.error ?? "the gate did not answer");
        setFindings(body.findings ?? []);
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "the gate did not answer");
      }
    })();
    return () => {
      live = false;
    };
  }, [theme]);

  const errors = (findings ?? []).filter((finding) => finding.severity === "error");
  const warnings = (findings ?? []).filter((finding) => finding.severity === "warn");

  return (
    <Section
      subtitle="Fourteen roles per mode. The ratios are marklib's, computed now against this palette."
      title="Colour"
    >
      {error ? <Problem text={error} /> : null}
      <div className="grid gap-6 lg:grid-cols-2">
        {(["light", "dark"] as const).map((mode) => (
          <div className="rounded-lg border p-4" key={mode}>
            <p className="mb-3 font-medium text-sm capitalize">{mode}</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {ROLES.map((role) => (
                <div className="flex items-center gap-2" key={role}>
                  <span
                    aria-hidden
                    className="size-8 shrink-0 rounded border"
                    style={{ background: theme[mode][role] }}
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-xs">{role}</span>
                    <span className="block font-mono text-[10px] text-muted-foreground uppercase">
                      {theme[mode][role]}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {findings === undefined ? null : (
        <div className="mt-4">
          <p className={cn("text-sm", errors.length > 0 ? "text-destructive" : "text-muted-foreground")}>
            {errors.length === 0
              ? `No unreadable pairs. ${warnings.length} pair${warnings.length === 1 ? "" : "s"} flagged to look at.`
              : `${errors.length} unreadable pair${errors.length === 1 ? "" : "s"}.`}
          </p>
          {findings.length === 0 ? null : (
            <ul className="mt-2 grid gap-1 sm:grid-cols-2">
              {findings.map((finding) => (
                <li
                  className="flex items-baseline justify-between gap-3 rounded border px-2 py-1 font-mono text-xs"
                  key={`${finding.mode}-${finding.foregroundRole}-${finding.backgroundRole}`}
                >
                  <span className="truncate">
                    {finding.foregroundRole} on {finding.backgroundRole}{" "}
                    <span className="text-muted-foreground">({finding.mode})</span>
                  </span>
                  <span className={finding.severity === "error" ? "text-destructive" : "text-muted-foreground"}>
                    {finding.ratio}:1 / {finding.minimum}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Section>
  );
}

function IdentityPanel({ spec }: { readonly spec: BrandSpec }) {
  const { identity } = spec;
  return (
    <Section subtitle="What the brand is for, and the rules that follow from it." title="Identity">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Field label="Positioning" value={identity.positioning} />
          <Field label="Story" value={identity.story} />
          {identity.legalName ? <Field label="Legal name" value={identity.legalName} /> : null}
        </div>
        <div className="flex flex-col gap-4">
          <Rules label="Voice" rules={identity.voice} />
          <Rules label="Usage" rules={identity.usageRules} />
        </div>
      </div>
    </Section>
  );
}

function TypographyPanel({ theme }: { readonly theme: Theme }) {
  const { typography, metrics } = theme;
  return (
    <Section subtitle="Names and sources. A stack without a source is a brand the browser silently substitutes." title="Type">
      <div className="grid gap-6 lg:grid-cols-2">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <Row label="Sans" value={typography.sans} />
          <Row label="Mono" value={typography.mono} />
          {typography.display ? <Row label="Display" value={typography.display} /> : null}
          <Row label="Base size" value={`${typography.baseSizePx}px`} />
          <Row label="Heading weight" value={String(typography.headingWeight)} />
          <Row label="Body weight" value={String(typography.bodyWeight)} />
          <Row label="Heading tracking" value={typography.headingTracking} />
          <Row label="Radius / unit" value={`${metrics.radiusPx}px / ${metrics.unitPx}px`} />
        </dl>
        <ul className="flex flex-col gap-2 text-sm">
          {typography.fonts.map((font) => (
            <li className="rounded border px-3 py-2" key={`${font.family}-${font.weight}-${font.style ?? "normal"}`}>
              <p className="font-medium">
                {font.family} <span className="text-muted-foreground">{font.weight}</span>
                {font.style === "italic" ? <span className="text-muted-foreground"> italic</span> : null}
              </p>
              <p className="mt-0.5 break-all font-mono text-[11px] text-muted-foreground">{font.srcUri}</p>
              <p className="mt-0.5 text-muted-foreground text-xs">{font.license}</p>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}

function ProductionPanel({ spec }: { readonly spec: BrandSpec }) {
  return (
    <Section subtitle="What a complete build produces, and the words the templates use." title="Production">
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <p className="mb-2 font-medium text-sm">Catalog</p>
          <ul className="flex flex-wrap gap-1">
            {spec.catalog.kinds.map((kind) => (
              <li className="rounded border px-2 py-0.5 font-mono text-[11px]" key={kind}>
                {kind.replace("ARTIFACT_KIND_", "").toLowerCase()}
              </li>
            ))}
            {(spec.catalog.custom ?? []).map((custom) => (
              <li className="rounded border border-dashed px-2 py-0.5 font-mono text-[11px]" key={custom}>
                {custom}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-muted-foreground text-xs">
            Mark sizes {spec.mark.sizes.join(", ")} · layers {spec.mark.layers.join(", ")} · variants{" "}
            {spec.mark.variants.join(", ")}
          </p>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <Row label="Deck title" value={spec.copy.deckTitle} />
          <Row label="Subtitle" value={spec.copy.deckSubtitle} />
          <Row label="Mark section" value={spec.copy.markSectionTitle} />
          <Row label="Colour section" value={spec.copy.colorSectionTitle} />
          <Row label="Type section" value={spec.copy.typeSectionTitle} />
          <Row label="Closing" value={spec.copy.closing} />
        </dl>
      </div>
    </Section>
  );
}

function Section({
  children,
  subtitle,
  title,
}: {
  readonly children: React.ReactNode;
  readonly subtitle: string;
  readonly title: string;
}) {
  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="font-medium text-xl tracking-tight">{title}</h2>
        <p className="text-muted-foreground text-sm">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function Field({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div>
      <p className="font-medium text-sm">{label}</p>
      <p className="mt-1 text-muted-foreground text-sm leading-relaxed">{value}</p>
    </div>
  );
}

function Rules({ label, rules }: { readonly label: string; readonly rules: readonly string[] }) {
  return (
    <div>
      <p className="font-medium text-sm">{label}</p>
      <ul className="mt-1 flex flex-col gap-1">
        {rules.map((rule) => (
          <li className="text-muted-foreground text-sm leading-relaxed" key={rule}>
            — {rule}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Row({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate">{value}</dd>
    </>
  );
}

function Problem({ text }: { readonly text: string }) {
  return (
    <p className="flex items-start gap-2 rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm">
      <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-destructive" />
      <span>{text}</span>
    </p>
  );
}

/** `mark_flat.svg` → `flat`. The emitter names files after the variant. */
function variantOf(filename: string): string {
  return filename.replace(/^mark_/, "").replace(/\.svg$/, "");
}

/**
 * `mark_flat.svg` yes, `mark_flat.body.svg` no.
 *
 * The service returns each LAYER as its own file beside the composite, because
 * a build needs them separately — an icon pack masks one layer, the app icon
 * composites all of them. A brand page wants the mark, so the layer files are
 * data this view does not show rather than data it does not ask for.
 */
function isComposite(filename: string): boolean {
  return filename.split(".").length === 2;
}

/**
 * The ground a variant is meant to sit on, so a light mark is not shown on
 * white. `transparent` is named exactly that by contract, and gets a checker
 * board rather than a colour.
 */
function groundFor(filename: string, theme: Theme): string {
  const variant = variantOf(filename);
  if (variant.includes("transparent")) {
    return "repeating-conic-gradient(#0000000d 0% 25%, transparent 0% 50%) 50% / 16px 16px";
  }
  return variant.includes("dark") ? theme.dark.bg : theme.light.bg;
}

function toBase64(svg: string): string {
  // btoa is Latin-1; SVG is UTF-8, and a brand with a non-ASCII layer name or
  // title would throw rather than render.
  const bytes = new TextEncoder().encode(svg);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
