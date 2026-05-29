import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import type { LayoutMap } from '$lib/linkml/toFlow';
import { layoutPath, writeLayout } from '$lib/server/store';

/** Writes node positions to the `.bp.json` neighbor file. */
export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json();
	if (!body?.layout || typeof body.layout !== 'object') {
		throw error(400, 'Expected { layout: Record<string, {x,y}> }');
	}
	if (!layoutPath()) throw error(409, 'Not file-backed');
	writeLayout(body.layout as LayoutMap);
	return json({ ok: true });
};
