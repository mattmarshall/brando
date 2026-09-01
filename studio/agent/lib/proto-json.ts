/**
 * The zod shapes, as protobuf messages.
 *
 * THE BUG THIS FILE EXISTS FOR. Both shapes were built to mirror the same
 * protos, so the obvious conversion is `create(Schema, value)` — and it
 * typechecks, because the cast that makes it compile also hides what is wrong
 * with it. `create()` takes protobuf-es's OBJECT form, in which a oneof is a
 * tagged `{ case, value }` pair; proto3 JSON — which is what `brand.ts`
 * describes, deliberately — spells a oneof as a plain field. So
 * `{ name: "w", value: "10" }` reached the service as a `Param` with no member
 * set at all, and every mark render failed with "parameter 'w' sets none of
 * value/list/table".
 *
 * It failed loudly, which is the only good thing about it. But nothing caught
 * it before the service did: `studio/tests/brando-client.test.ts` builds its
 * messages with `create()` and tagged oneofs, so it exercised the transport and
 * the interpreter without ever exercising the conversion the AGENTS use.
 *
 * `fromJson` is the conversion that matches. It is protobuf's own proto3-JSON
 * reader: flat oneof members, `lowerCamelCase` or original field names, enums by
 * name. It also rejects a field the proto does not have, which is the property
 * that makes it a gate rather than a cast — a zod schema that drifts from the
 * proto now fails here instead of arriving as a silently emptier message.
 */
import { fromJson, type JsonValue } from "@bufbuild/protobuf";

import type { BrandSpec, MarkProgram } from "./brand";
import { BrandSpecSchema, MarkProgramSchema } from "./brando/gen/brando/v1/brand_pb";

export function toMarkProgramMessage(program: MarkProgram) {
  return fromJson(MarkProgramSchema, program as unknown as JsonValue);
}

export function toBrandSpecMessage(spec: Partial<BrandSpec>) {
  return fromJson(BrandSpecSchema, spec as unknown as JsonValue);
}
