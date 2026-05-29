import { describe, it, expect } from 'vitest';
import { neighborPath } from './paths';

describe('neighborPath', () => {
	it('replaces a .yaml extension', () => {
		expect(neighborPath('mydb.yaml')).toBe('mydb.bp.json');
		expect(neighborPath('/abs/path/mydb.yaml')).toBe('/abs/path/mydb.bp.json');
	});

	it('replaces a .yml extension', () => {
		expect(neighborPath('mydb.yml')).toBe('mydb.bp.json');
	});

	it('is case-insensitive on the extension', () => {
		expect(neighborPath('MyDb.YAML')).toBe('MyDb.bp.json');
	});

	it('keeps compound stems', () => {
		expect(neighborPath('schema.linkml.yaml')).toBe('schema.linkml.bp.json');
	});

	it('strips a non-yaml extension', () => {
		expect(neighborPath('weird.txt')).toBe('weird.bp.json');
	});

	it('appends when there is no extension', () => {
		expect(neighborPath('/data/mydb')).toBe('/data/mydb.bp.json');
	});

	it('does not treat a dotted directory as an extension', () => {
		expect(neighborPath('/has.dot/dir/mydb')).toBe('/has.dot/dir/mydb.bp.json');
	});
});
