"use client";

/**
 * The brief, as the client walks in with it.
 *
 * FOUR FIELDS, MATCHING `briefSchema` EXACTLY. A free-text box would work — the
 * director would parse it — but the id is the archive's basename and has a
 * shape (`^[a-z][a-z0-9_]*$`), and discovering that from a rejection after the
 * agency has already started is a worse experience than a field that says so.
 * `constraints` is separate for the reason the schema gives it its own field:
 * silently overriding a colour a client has already decided is the worst thing
 * this studio can do, so it does not arrive buried in a paragraph.
 */
import { useState } from "react";

import { briefSchema, type Brief } from "@/agent/lib/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

/** `Leangres Studio` → `leangres_studio`, the archive's basename. */
function slugify(displayName: string): string {
  const slug = displayName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/^([^a-z])/, "b$1");
  return slug.slice(0, 40);
}

export function BriefForm({ onSubmit }: { readonly onSubmit: (brief: Brief) => void }) {
  const [displayName, setDisplayName] = useState("");
  const [brandId, setBrandId] = useState("");
  const [idEdited, setIdEdited] = useState(false);
  const [brief, setBrief] = useState("");
  const [constraints, setConstraints] = useState("");
  const [problems, setProblems] = useState<readonly string[]>([]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const candidate = {
      brandId: (idEdited ? brandId : slugify(displayName)).trim(),
      brief: brief.trim(),
      constraints: constraints.trim() || undefined,
      displayName: displayName.trim(),
    };
    const parsed = briefSchema.safeParse(candidate);
    if (!parsed.success) {
      setProblems(
        parsed.error.issues.map((issue) => `${issue.path.join(".") || "brief"}: ${issue.message}`),
      );
      return;
    }
    setProblems([]);
    onSubmit(parsed.data);
  };

  return (
    <form className="flex w-full flex-col gap-5" onSubmit={submit}>
      <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
        <label className="flex flex-col gap-1.5">
          <span className="font-medium text-sm">Name</span>
          <Input
            onChange={(event) => {
              setDisplayName(event.currentTarget.value);
              if (!idEdited) setBrandId(slugify(event.currentTarget.value));
            }}
            placeholder="Leangres"
            value={displayName}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-medium text-sm">Id</span>
          <Input
            className="font-mono"
            onChange={(event) => {
              setIdEdited(true);
              setBrandId(event.currentTarget.value);
            }}
            placeholder="leangres"
            value={idEdited ? brandId : slugify(displayName)}
          />
        </label>
      </div>

      <label className="flex flex-col gap-1.5">
        <span className="font-medium text-sm">Brief</span>
        <Textarea
          className="min-h-32"
          onChange={(event) => setBrief(event.currentTarget.value)}
          placeholder="What the brand is for, who it is for, and what it must not look like."
          value={brief}
        />
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="font-medium text-sm">
          Already decided <span className="font-normal text-muted-foreground">(optional)</span>
        </span>
        <Textarea
          className="min-h-20"
          onChange={(event) => setConstraints(event.currentTarget.value)}
          placeholder="Colours, faces or metrics that are not up for discussion."
          value={constraints}
        />
      </label>

      {problems.length === 0 ? null : (
        <ul className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}

      <Button className="self-start" type="submit">
        Brief the studio
      </Button>
    </form>
  );
}

/**
 * The brief as the director's first message.
 *
 * Labelled lines rather than JSON: `parse_brief` is a tool call the director
 * makes, and the fields are named the same on both sides, so this is the
 * shortest thing that cannot be misread.
 */
export function briefMessage(brief: Brief): string {
  const lines = [
    `Brand id: ${brief.brandId}`,
    `Display name: ${brief.displayName}`,
    "",
    "Brief:",
    brief.brief,
  ];
  if (brief.constraints) {
    lines.push("", "Already decided (hard constraints):", brief.constraints);
  }
  return lines.join("\n");
}
