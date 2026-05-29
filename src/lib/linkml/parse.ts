import { parse as parseYaml } from 'yaml';
import type { ParsedSchema, ParsedClass, ParsedSlot, ForeignKey, SchemaProblem } from './types';

/**
 * LinkML builtin scalar types. A slot's `range` resolves to one of these, a
 * schema-defined `type`/`enum` (a scalar column), or a class (a foreign key).
 * Anything else is a broken reference and is reported as a problem.
 *
 * @see https://linkml.io/linkml-model/latest/docs/specification/03types/
 */
const BUILTIN_TYPES = new Set([
	'string',
	'integer',
	'boolean',
	'float',
	'double',
	'decimal',
	'time',
	'date',
	'datetime',
	'uriorcurie',
	'curie',
	'uri',
	'ncname',
	'objectidentifier',
	'nodeidentifier',
	'jsonpointer',
	'jsonpath',
	'sparqlpath'
]);

/** Loosely-typed view of a raw LinkML document after YAML parsing. */
interface RawSchema {
	name?: string;
	title?: string;
	description?: string;
	default_range?: string;
	imports?: string[];
	classes?: Record<string, RawClass>;
	slots?: Record<string, RawSlot>;
	types?: Record<string, unknown>;
	enums?: Record<string, unknown>;
}

interface RawClass {
	description?: string;
	is_a?: string;
	mixins?: string[];
	slots?: string[];
	attributes?: Record<string, RawSlot>;
	slot_usage?: Record<string, RawSlot>;
}

interface RawSlot {
	range?: string;
	required?: boolean;
	multivalued?: boolean;
	identifier?: boolean;
	key?: boolean;
	description?: string;
	inlined?: boolean;
	inlined_as_list?: boolean;
}

export interface ParseOptions {
	/**
	 * Resolve a LinkML `imports:` entry to the imported file's YAML text. Return
	 * `null` to skip it (e.g. metamodel CURIEs like `linkml:types`, or a file that
	 * can't be found). Without a resolver, `imports` are ignored — fine for the
	 * browser, where there's no filesystem; see `$lib/server/parseFile` for disk.
	 */
	resolveImport?: (name: string) => string | null;
}

/** Merge imported definitions under the importing doc, which wins on name conflicts. */
function mergeImport(into: RawSchema, from: RawSchema): void {
	into.classes = { ...(from.classes ?? {}), ...(into.classes ?? {}) };
	into.slots = { ...(from.slots ?? {}), ...(into.slots ?? {}) };
	into.types = { ...(from.types ?? {}), ...(into.types ?? {}) };
	into.enums = { ...(from.enums ?? {}), ...(into.enums ?? {}) };
}

/** Parse a doc and recursively fold its `imports` into one combined raw schema. */
function resolveImports(
	yamlText: string,
	resolve: ParseOptions['resolveImport'],
	seen: Set<string>
): RawSchema {
	const doc = (parseYaml(yamlText) ?? {}) as RawSchema;
	if (!resolve || !Array.isArray(doc.imports)) return doc;
	for (const name of doc.imports) {
		if (seen.has(name)) continue;
		seen.add(name);
		const text = resolve(name);
		if (text == null) continue;
		mergeImport(doc, resolveImports(text, resolve, seen));
	}
	return doc;
}

/**
 * Parse a LinkML YAML document into the ER model we render.
 *
 * Supports the commonly-used subset: top-level `classes` with inline
 * `attributes` and/or referenced `slots`, reusable top-level `slots`,
 * `slot_usage` overrides, `is_a` / `mixins` inheritance, and `imports` (when a
 * resolver is supplied). Slots and attributes are treated interchangeably, and
 * imported slots/classes/types/enums are merged before interpretation — so a
 * schema that imports its slots from another file builds the same canvas as the
 * equivalent single-file, attribute-based schema.
 */
export function parseLinkML(yamlText: string, opts: ParseOptions = {}): ParsedSchema {
	const doc = resolveImports(yamlText, opts.resolveImport, new Set());

	const rawClasses = doc.classes ?? {};
	const rawSlots = doc.slots ?? {};
	const defaultRange = doc.default_range ?? 'string';

	const classNames = new Set(Object.keys(rawClasses));
	// Ranges that resolve to a scalar column rather than a relationship.
	const scalarRanges = new Set<string>([
		...BUILTIN_TYPES,
		...Object.keys(doc.types ?? {}),
		...Object.keys(doc.enums ?? {})
	]);

	/** Merge slot definition layers (top-level slot → local def → slot_usage) into one resolved slot. */
	function resolveSlot(name: string, ...layers: (RawSlot | undefined)[]): ParsedSlot {
		const merged: RawSlot = Object.assign({}, rawSlots[name], ...layers.map((l) => l ?? {}));
		const range = merged.range ?? defaultRange;
		const isClassRef = classNames.has(range);
		return {
			name,
			range,
			required: !!merged.required,
			multivalued: !!merged.multivalued,
			identifier: !!merged.identifier,
			key: !!merged.key,
			description: merged.description,
			inlined: !!merged.inlined || !!merged.inlined_as_list,
			refClass: isClassRef ? range : undefined,
			unresolved: !isClassRef && !scalarRanges.has(range)
		};
	}

	/** Collect a class's slots, applying inheritance. Child slots override inherited ones by name. */
	function classSlots(className: string, seen = new Set<string>()): ParsedSlot[] {
		if (seen.has(className)) return [];
		seen.add(className);
		const c = rawClasses[className];
		if (!c) return [];

		const slots = new Map<string, ParsedSlot>();

		// Inherited slots first, so own definitions take precedence.
		if (c.is_a) for (const s of classSlots(c.is_a, seen)) slots.set(s.name, s);
		if (Array.isArray(c.mixins))
			for (const m of c.mixins) for (const s of classSlots(m, seen)) slots.set(s.name, s);

		const usage = c.slot_usage ?? {};

		// Slots referenced by name from the top-level `slots` block.
		if (Array.isArray(c.slots))
			for (const sn of c.slots) slots.set(sn, resolveSlot(sn, rawSlots[sn], usage[sn]));

		// Inline attribute definitions.
		if (c.attributes)
			for (const [sn, def] of Object.entries(c.attributes))
				slots.set(sn, resolveSlot(sn, def, usage[sn]));

		return [...slots.values()];
	}

	const classes: ParsedClass[] = Object.keys(rawClasses).map((name) => {
		const slots = classSlots(name);
		const idSlot = slots.find((s) => s.identifier) ?? slots.find((s) => s.key);
		return {
			name,
			description: rawClasses[name]?.description,
			isA: rawClasses[name]?.is_a,
			slots,
			identifierSlot: idSlot?.name
		};
	});

	const byName = new Map(classes.map((c) => [c.name, c]));
	const foreignKeys: ForeignKey[] = [];
	const problems: SchemaProblem[] = [];
	for (const c of classes) {
		for (const s of c.slots) {
			if (s.unresolved) {
				problems.push({
					level: 'error',
					className: c.name,
					slot: s.name,
					message: `range "${s.range}" is not a known class, type, or enum`
				});
				continue;
			}
			if (!s.refClass) continue;
			foreignKeys.push({
				id: `${c.name}.${s.name}->${s.refClass}`,
				fromClass: c.name,
				fromSlot: s.name,
				toClass: s.refClass,
				toSlot: byName.get(s.refClass)?.identifierSlot,
				multivalued: s.multivalued,
				required: s.required
			});
		}
	}

	return {
		name: doc.name ?? 'schema',
		title: doc.title,
		description: doc.description,
		classes,
		foreignKeys,
		problems
	};
}
