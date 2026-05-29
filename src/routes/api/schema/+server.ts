import { json, error } from '@sveltejs/kit';
import { basename } from 'node:path';
import type { RequestHandler } from './$types';
import { schemaPath, layoutPath, readSchema, readLayout, writeSchema } from '$lib/server/store';

/** Returns the on-disk schema + layout, or `serverBacked: false` in browser mode. */
export const GET: RequestHandler = () => {
	const path = schemaPath();
	if (!path) return json({ serverBacked: false });

	const yaml = readSchema();
	return json({
		serverBacked: true,
		path,
		fileName: basename(path),
		layoutPath: layoutPath(),
		layoutName: layoutPath() ? basename(layoutPath()!) : null,
		missing: yaml === null,
		yaml: yaml ?? '',
		layout: readLayout()
	});
};

/** Persists edited schema text back to the source file. */
export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json();
	if (typeof body?.yaml !== 'string') throw error(400, 'Expected { yaml: string }');
	if (!schemaPath()) throw error(409, 'Not file-backed');
	writeSchema(body.yaml);
	return json({ ok: true });
};
