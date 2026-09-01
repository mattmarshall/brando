"use client";

/**
 * The studio floor: who is working, and what has been measured.
 *
 * The wave layout is the director's own instruction made visible — wave 1 has
 * no dependencies, wave 2 needs the theme, wave 3 needs the mark, wave 4 needs
 * everything — so a run that serialises what should be concurrent is something
 * you can see rather than something you have to read a log to find.
 */
import { CheckIcon, LoaderIcon, TriangleAlertIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { WAVES } from "./roster";
import type { Fact, RunState, SpecialistStatus } from "./run-state";

export function Floor({ run }: { readonly run: RunState }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        {WAVES.map((wave, index) => (
          <div className="flex flex-col gap-2" key={`wave-${index + 1}`}>
            <p className="text-muted-foreground text-xs uppercase tracking-wide">Wave {index + 1}</p>
            <div className="flex flex-col gap-1.5">
              {wave.map((specialist) => (
                <SpecialistCard
                  key={specialist.id}
                  status={
                    run.statuses.find((status) => status.specialist.id === specialist.id) ?? {
                      specialist,
                      state: "idle",
                    }
                  }
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {run.facts.length === 0 ? null : <Ledger facts={run.facts} />}
    </div>
  );
}

function SpecialistCard({ status }: { readonly status: SpecialistStatus }) {
  const { specialist, state } = status;
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg border px-3 py-2 transition-colors",
        state === "working" && "border-foreground/30 bg-muted/40",
        state === "idle" && "opacity-50",
        state === "failed" && "border-destructive/40",
      )}
    >
      <span className="mt-0.5 shrink-0">
        {state === "working" ? <LoaderIcon className="size-3.5 animate-spin" /> : null}
        {state === "done" ? <CheckIcon className="size-3.5" /> : null}
        {state === "failed" ? <TriangleAlertIcon className="size-3.5 text-destructive" /> : null}
        {state === "idle" ? <span className="block size-3.5 rounded-full border" /> : null}
      </span>
      <span className="min-w-0">
        <span className="block font-medium text-sm">{specialist.title}</span>
        <span className="block text-muted-foreground text-xs">{specialist.owns}</span>
      </span>
    </div>
  );
}

/**
 * What brando was asked, and what it answered.
 *
 * Separate from the specialists on purpose: these are the only lines on the
 * page that are arithmetic rather than judgement, and the studio's whole claim
 * is that the two are kept apart.
 */
function Ledger({ facts }: { readonly facts: readonly Fact[] }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-muted-foreground text-xs uppercase tracking-wide">Measured</p>
      <ul className="flex flex-col gap-1">
        {facts.map((fact) => (
          <li className="rounded border px-2.5 py-1.5 text-xs" key={fact.id}>
            <span className="font-mono">{fact.tool}</span>
            <span className={cn("mt-0.5 block", fact.failed ? "text-destructive" : "text-muted-foreground")}>
              {fact.summary}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
