import type { LayoutMap } from '$lib/linkml/toFlow';

/**
 * Persistence for the *where to paint* layer. Positions are stored separately
 * from the LinkML source so the schema stays the single source of truth while
 * users freely rearrange the canvas. Keyed by schema name in localStorage.
 */

const keyFor = (schema: string) => `blueprint:layout:${schema}`;

export function loadLayout(schema: string): LayoutMap {
	if (typeof localStorage === 'undefined') return {};
	try {
		const raw = localStorage.getItem(keyFor(schema));
		return raw ? (JSON.parse(raw) as LayoutMap) : {};
	} catch {
		return {};
	}
}

export function saveLayout(schema: string, layout: LayoutMap): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(keyFor(schema), JSON.stringify(layout));
}

export function clearLayout(schema: string): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.removeItem(keyFor(schema));
}
