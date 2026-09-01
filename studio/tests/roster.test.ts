/**
 * The UI's directory, held against the agency's.
 *
 * `app/_components/roster.ts` lists eight specialists and assigns them to
 * waves. The waves are a UI decision — they mirror prose in
 * `agent/instructions.md`, which there is nothing to import from. The ROSTER is
 * not: every id has to be a real subagent, or the floor shows a card that never
 * lights up, and a specialist added later would work perfectly while being
 * invisible. Both failures are silent, which is why this test exists.
 */
import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { ROSTER, SUBAGENT_TOOL_PREFIX, specialistFor, WAVES } from "../app/_components/roster";

const here = dirname(fileURLToPath(import.meta.url));

function subagentDirectories(): string[] {
  return readdirSync(join(here, "..", "agent", "subagents"), { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
}

test("the roster is exactly the agents under agent/subagents", () => {
  assert.deepEqual(
    ROSTER.map((specialist) => specialist.id).sort(),
    subagentDirectories(),
  );
});

test("every specialist is in exactly one wave", () => {
  const flattened = WAVES.flat().map((specialist) => specialist.id);
  assert.equal(flattened.length, ROSTER.length);
  assert.equal(new Set(flattened).size, ROSTER.length);
});

test("a delegation tool name resolves to its specialist", () => {
  for (const specialist of ROSTER) {
    assert.equal(specialistFor(`${SUBAGENT_TOOL_PREFIX}${specialist.id}`)?.id, specialist.id);
  }
});

test("an ordinary tool call is not mistaken for a delegation", () => {
  // `check_contrast` and `submit_brand` arrive in the same stream and with the
  // same part type. Reading one as a specialist would light a card at random.
  assert.equal(specialistFor("check_contrast"), undefined);
  assert.equal(specialistFor("submit_brand"), undefined);
  assert.equal(specialistFor(`${SUBAGENT_TOOL_PREFIX}not_a_specialist`), undefined);
});
