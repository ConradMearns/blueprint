import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { env } from '$env/dynamic/private';
import { neighborPath } from './paths';
import type { LayoutMap } from '$lib/linkml/toFlow';

/**
 * Filesystem-backed store for the `bp` CLI. The target schema is passed in via
 * the `BP_FILE` env var (set by `bin/bp.js`); the layout lives in a neighbor
 * `.bp.json` file, overridable with `BP_LAYOUT`. When `BP_FILE` is unset the app
 * runs in plain browser mode (bundled example + localStorage) and these helpers
 * report "no file".
 */

/** Absolute path to the schema file the CLI was pointed at, or null in browser mode. */
export function schemaPath(): string | null {
	return env.BP_FILE ? resolve(env.BP_FILE) : null;
}

/** Absolute path to the layout neighbor file, or null in browser mode. */
export function layoutPath(): string | null {
	const target = schemaPath();
	if (!target) return null;
	return env.BP_LAYOUT ? resolve(env.BP_LAYOUT) : neighborPath(target);
}

// The exact text/JSON we last wrote, so the file watcher can tell our own
// saves apart from genuine external edits and avoid an echo loop.
let lastSchemaWrite: string | null = null;
let lastLayoutWrite: string | null = null;
export const lastWrittenSchema = (): string | null => lastSchemaWrite;
export const lastWrittenLayout = (): string | null => lastLayoutWrite;

export function readSchema(): string | null {
	const target = schemaPath();
	if (!target || !existsSync(target)) return null;
	return readFileSync(target, 'utf8');
}

export function readLayout(): LayoutMap {
	const path = layoutPath();
	if (!path || !existsSync(path)) return {};
	try {
		return JSON.parse(readFileSync(path, 'utf8')) as LayoutMap;
	} catch {
		return {};
	}
}

export function writeLayout(layout: LayoutMap): void {
	const path = layoutPath();
	if (!path) throw new Error('No layout file configured (browser mode)');
	const out = `${JSON.stringify(layout, null, 2)}\n`;
	lastLayoutWrite = out;
	writeFileSync(path, out);
}

export function writeSchema(yaml: string): void {
	const target = schemaPath();
	if (!target) throw new Error('No schema file configured (browser mode)');
	lastSchemaWrite = yaml;
	writeFileSync(target, yaml);
}
