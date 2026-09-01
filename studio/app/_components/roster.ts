/**
 * The studio's directory, in the order the director works it.
 *
 * WHY THIS LIST IS DUPLICATED HERE AND NOT DERIVED. The waves are stated in
 * `agent/instructions.md`, which is prose the model reads — there is nothing to
 * import. What this file must not do is invent a specialist: every `id` below
 * is a directory under `agent/subagents/`, and `tests/roster.test.ts` reads
 * that directory and fails if the two disagree. So the wave numbers are a UI
 * decision and the roster is not.
 */
export type Specialist = {
  readonly id: string;
  readonly title: string;
  /** What this one is answerable for, in the brand rather than in the app. */
  readonly owns: string;
  readonly wave: number;
};

export const ROSTER: readonly Specialist[] = [
  { id: "strategist", title: "Strategist", owns: "tagline, positioning, story, voice", wave: 1 },
  { id: "colorist", title: "Colorist", owns: "both palettes, gated on contrast", wave: 1 },
  { id: "typographer", title: "Typographer", owns: "the stacks, their sources, the metrics", wave: 1 },
  { id: "mark_designer", title: "Mark designer", owns: "the mark, as parametric geometry", wave: 2 },
  { id: "wordmark_designer", title: "Wordmark designer", owns: "the wordmark and the lockup", wave: 2 },
  { id: "platform_producer", title: "Platform producer", owns: "which artifacts a build produces", wave: 3 },
  { id: "brandbook_author", title: "Brandbook author", owns: "the copy the templates use", wave: 3 },
  { id: "critic", title: "Critic", owns: "what the brand says versus what it is", wave: 4 },
];

export const WAVES: readonly (readonly Specialist[])[] = [1, 2, 3, 4].map((wave) =>
  ROSTER.filter((specialist) => specialist.wave === wave),
);

/** eve names a delegation `eve:subagent:<id>`; this is the only place that knows. */
export const SUBAGENT_TOOL_PREFIX = "eve:subagent:";

export function specialistFor(toolName: string): Specialist | undefined {
  if (!toolName.startsWith(SUBAGENT_TOOL_PREFIX)) return undefined;
  const id = toolName.slice(SUBAGENT_TOOL_PREFIX.length);
  return ROSTER.find((specialist) => specialist.id === id);
}
