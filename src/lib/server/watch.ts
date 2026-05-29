import { watch, type FSWatcher } from 'chokidar';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { LayoutMap } from '$lib/linkml/toFlow';
import { schemaPath, layoutPath, lastWrittenSchema, lastWrittenLayout } from './store';

/**
 * Watches the target schema file and its `.bp.json` neighbor and notifies
 * subscribers (SSE connections) when they change on disk. Writes the app made
 * itself are suppressed by comparing against the last-written content, so an
 * autosave doesn't bounce back as an external change.
 *
 * One chokidar watcher is shared across all subscribers, created lazily.
 */

export type WatchEvent = { type: 'schema'; yaml: string } | { type: 'layout'; layout: LayoutMap };

type Subscriber = (event: WatchEvent) => void;

const subscribers = new Set<Subscriber>();
let watcher: FSWatcher | null = null;

function handleChange(changed: string) {
	const path = resolve(changed);
	const schema = schemaPath();
	const layout = layoutPath();

	if (schema && path === schema && existsSync(schema)) {
		const yaml = readFileSync(schema, 'utf8');
		if (yaml === lastWrittenSchema()) return; // our own save
		emit({ type: 'schema', yaml });
	} else if (layout && path === layout && existsSync(layout)) {
		const raw = readFileSync(layout, 'utf8');
		if (raw === lastWrittenLayout()) return; // our own save
		try {
			emit({ type: 'layout', layout: JSON.parse(raw) as LayoutMap });
		} catch {
			// ignore a partially-written / invalid layout file
		}
	}
}

function emit(event: WatchEvent) {
	for (const sub of subscribers) sub(event);
}

function ensureWatcher() {
	if (watcher) return;
	const schema = schemaPath();
	if (!schema) return;

	const paths = [schema];
	const layout = layoutPath();
	if (layout) paths.push(layout);

	watcher = watch(paths, {
		ignoreInitial: true,
		// Settle multi-event saves (and editors that write-then-rename) before reading.
		awaitWriteFinish: { stabilityThreshold: 80, pollInterval: 20 }
	});
	// 'add' covers editors that replace the file via atomic rename.
	watcher.on('change', handleChange);
	watcher.on('add', handleChange);
}

/** Register an SSE connection. Returns an unsubscribe function. */
export function subscribe(cb: Subscriber): () => void {
	ensureWatcher();
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}
