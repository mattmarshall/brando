import { disableTool } from "eve/tools";

/**
 * The generic self-delegation tool, off.
 *
 * The studio delegates only to its eight declared specialists, each of which
 * has an output schema and a required tool sequence. A free-form `agent` call
 * is both unnecessary here and strictly less constrained than the roster —
 * it would let the director invent a tenth specialist with no contract, which
 * is the failure mode the roster exists to prevent. humblebrag disables it for
 * the same reason.
 */
export default disableTool();
