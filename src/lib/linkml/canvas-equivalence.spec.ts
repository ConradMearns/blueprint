import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { parseLinkML } from './parse';
import { parseLinkMLFile } from '$lib/server/parseFile';
import { canvasFingerprint, type CanvasFingerprint } from './fingerprint';

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = resolve(here, 'fixtures');
const examplePath = resolve(here, '../examples/ecommerce.linkml.yaml');

/**
 * The committed known-good canvas, generated from the attribute-based ecommerce
 * schema. Every alternative representation of the same database must reproduce
 * it. See `fixtures/README.md` for what each variant file should contain.
 */
const knownGood: CanvasFingerprint = JSON.parse(
	readFileSync(resolve(fixtures, 'ecommerce.canvas.json'), 'utf8')
);

describe('canvas baseline (attribute-based ecommerce)', () => {
	it('parses to the committed known-good canvas', () => {
		expect(canvasFingerprint(parseLinkML(readFileSync(examplePath, 'utf8')))).toEqual(knownGood);
	});
});

/**
 * Each variant should describe the same database as the attribute baseline.
 * Drop the file into `fixtures/` and its test activates automatically; until
 * then it is skipped (so CI stays green). Import-based variants are parsed via
 * `parseLinkMLFile`, which resolves `imports:` relative to the file.
 */
const variants = [
	{ label: 'slot-based, single file', file: 'ecommerce.slots.yaml' },
	{ label: 'attribute-based with import', file: 'ecommerce.attributes-import.yaml' },
	{ label: 'slot-based with import', file: 'ecommerce.slots-import.yaml' }
];

describe('slot / attribute / import equivalence', () => {
	for (const { label, file } of variants) {
		const path = resolve(fixtures, file);
		const test = existsSync(path) ? it : it.skip;
		test(`${label} → same canvas as baseline (${file})`, () => {
			expect(canvasFingerprint(parseLinkMLFile(path))).toEqual(knownGood);
		});
	}
});
