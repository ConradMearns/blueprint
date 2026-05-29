/**
 * Minimal type model for the subset of LinkML we interpret as an ER diagram.
 *
 * LinkML is the *source of truth* for what to draw. We never store node
 * positions here — layout lives in a separate file (see `$lib/layout`).
 */

export interface ParsedSlot {
	/** Slot (column) name as written in the schema. */
	name: string;
	/** Resolved range — a builtin type, an enum, or another class name. */
	range: string;
	required: boolean;
	multivalued: boolean;
	/** True when `identifier: true` — the primary key. */
	identifier: boolean;
	/** True when `key: true` — a unique key (treated like a PK for layout). */
	key: boolean;
	description?: string;
	/** True when the related object is embedded rather than referenced. */
	inlined: boolean;
	/** Set when `range` resolves to another class in the schema (a foreign key). */
	refClass?: string;
}

export interface ParsedClass {
	name: string;
	description?: string;
	/** Parent class via `is_a`, if any. */
	isA?: string;
	/** Resolved slots, including inherited ones. */
	slots: ParsedSlot[];
	/** Name of the identifier/key slot, if the class declares one. */
	identifierSlot?: string;
}

/** A relationship between two classes derived from a slot whose range is a class. */
export interface ForeignKey {
	id: string;
	fromClass: string;
	fromSlot: string;
	toClass: string;
	/** Identifier slot of the target class, if it has one. */
	toSlot?: string;
	multivalued: boolean;
	required: boolean;
}

export interface ParsedSchema {
	name: string;
	title?: string;
	description?: string;
	classes: ParsedClass[];
	foreignKeys: ForeignKey[];
}
