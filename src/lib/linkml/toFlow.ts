import { MarkerType, type Node, type Edge } from '@xyflow/svelte';
import type { ParsedSchema } from './types';

/** Map of class name → canvas position. This is the *where to paint* file. */
export type LayoutMap = Record<string, { x: number; y: number }>;

/** A single column rendered inside a table node. */
export interface TableColumn {
	name: string;
	type: string;
	pk: boolean;
	fk: boolean;
	required: boolean;
	multivalued: boolean;
	/** True when the column's range does not resolve to a known class/type/enum. */
	unresolved: boolean;
}

/** Data payload carried by a `table` node. Index signature keeps xyflow's `Node` happy. */
export interface TableNodeData {
	name: string;
	description?: string;
	identifierSlot?: string;
	columns: TableColumn[];
	[key: string]: unknown;
}

export type TableNode = Node<TableNodeData, 'table'>;

const COLUMN_WIDTH = 340;
const ROW_HEIGHT = 260;

/**
 * Produce positions for any class that doesn't already have one, packing new
 * classes into a square-ish grid. Existing positions are preserved untouched —
 * this is what lets the user drag things around without the schema fighting back.
 */
export function autoLayout(schema: ParsedSchema, existing: LayoutMap = {}): LayoutMap {
	const layout: LayoutMap = { ...existing };
	const perRow = Math.max(1, Math.ceil(Math.sqrt(schema.classes.length)));
	let placed = 0;
	for (const c of schema.classes) {
		if (layout[c.name]) continue;
		layout[c.name] = {
			x: (placed % perRow) * COLUMN_WIDTH,
			y: Math.floor(placed / perRow) * ROW_HEIGHT
		};
		placed++;
	}
	return layout;
}

/** Convert a parsed schema + layout into SvelteFlow nodes and edges. */
export function schemaToFlow(
	schema: ParsedSchema,
	layout: LayoutMap
): { nodes: TableNode[]; edges: Edge[] } {
	const nodes: TableNode[] = schema.classes.map((c) => ({
		id: c.name,
		type: 'table',
		position: layout[c.name] ?? { x: 0, y: 0 },
		data: {
			name: c.name,
			description: c.description,
			identifierSlot: c.identifierSlot,
			columns: c.slots.map((s) => ({
				name: s.name,
				type: s.range,
				pk: s.identifier || s.key,
				fk: !!s.refClass,
				required: s.required,
				multivalued: s.multivalued,
				unresolved: s.unresolved
			}))
		}
	}));

	const edges: Edge[] = schema.foreignKeys.map((fk) => ({
		id: fk.id,
		source: fk.fromClass,
		sourceHandle: `s-${fk.fromSlot}`,
		target: fk.toClass,
		targetHandle: fk.toSlot ? `t-${fk.toSlot}` : undefined,
		type: 'smoothstep',
		label: fk.multivalued ? '1..*' : fk.required ? '1' : '0..1',
		markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 }
	}));

	return { nodes, edges };
}
