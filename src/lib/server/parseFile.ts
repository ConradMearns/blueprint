import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { parseLinkML, type ParseOptions } from '$lib/linkml/parse';
import type { ParsedSchema } from '$lib/linkml/types';

/**
 * Build an import resolver that reads sibling files from `baseDir`. LinkML
 * `imports:` entries are resolved relative to the importing file; CURIE-style
 * imports (e.g. `linkml:types`) are skipped — their types are builtins to us.
 * The import name may omit the `.yaml`/`.yml` extension.
 */
export function makeFileResolver(baseDir: string): NonNullable<ParseOptions['resolveImport']> {
	return (name) => {
		if (name.includes(':')) return null; // metamodel CURIE, not a file
		const candidates = /\.ya?ml$/i.test(name) ? [name] : [`${name}.yaml`, `${name}.yml`];
		for (const candidate of candidates) {
			const path = resolve(baseDir, candidate);
			if (existsSync(path)) return readFileSync(path, 'utf8');
		}
		return null;
	};
}

/** Parse a LinkML file from disk, resolving relative `imports` from its directory. */
export function parseLinkMLFile(filePath: string): ParsedSchema {
	const abs = resolve(filePath);
	return parseLinkML(readFileSync(abs, 'utf8'), { resolveImport: makeFileResolver(dirname(abs)) });
}
