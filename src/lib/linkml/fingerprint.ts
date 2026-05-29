import type { ParsedSchema } from './types';

/**
 * A normalized, order-independent snapshot of what the canvas draws for a
 * schema: the tables and their columns, the foreign-key edges, and any
 * validation problems. Mirrors the data `toFlow` turns into nodes/edges, minus
 * positions (which live in the separate layout file).
 *
 * Two LinkML schemas that describe the same database — whether written with
 * inline `attributes`, top-level `slots`, or `slots` pulled in via `imports` —
 * must produce the same fingerprint. Everything is sorted by name so that
 * declaration order doesn't affect equality.
 */

export interface FingerprintColumn {
	name: string;
	type: string;
	pk: boolean;
	fk: boolean;
	required: boolean;
	multivalued: boolean;
	unresolved: boolean;
}

export interface FingerprintTable {
	name: string;
	columns: FingerprintColumn[];
}

export interface FingerprintEdge {
	fromClass: string;
	fromSlot: string;
	toClass: string;
	toSlot: string | null;
	required: boolean;
	multivalued: boolean;
}

export interface FingerprintProblem {
	level: string;
	className: string;
	slot: string;
	message: string;
}

export interface CanvasFingerprint {
	tables: FingerprintTable[];
	edges: FingerprintEdge[];
	problems: FingerprintProblem[];
}

const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name);

export function canvasFingerprint(schema: ParsedSchema): CanvasFingerprint {
	const tables: FingerprintTable[] = schema.classes
		.map((c) => ({
			name: c.name,
			columns: c.slots
				.map((s) => ({
					name: s.name,
					type: s.range,
					pk: s.identifier || s.key,
					fk: !!s.refClass,
					required: s.required,
					multivalued: s.multivalued,
					unresolved: s.unresolved
				}))
				.sort(byName)
		}))
		.sort(byName);

	const edges: FingerprintEdge[] = schema.foreignKeys
		.map((fk) => ({
			fromClass: fk.fromClass,
			fromSlot: fk.fromSlot,
			toClass: fk.toClass,
			toSlot: fk.toSlot ?? null,
			required: fk.required,
			multivalued: fk.multivalued
		}))
		.sort((a, b) => `${a.fromClass}.${a.fromSlot}`.localeCompare(`${b.fromClass}.${b.fromSlot}`));

	const problems: FingerprintProblem[] = schema.problems
		.map((p) => ({ level: p.level, className: p.className, slot: p.slot, message: p.message }))
		.sort((a, b) => `${a.className}.${a.slot}`.localeCompare(`${b.className}.${b.slot}`));

	return { tables, edges, problems };
}
