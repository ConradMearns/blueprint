/**
 * Compute the layout neighbor file for a LinkML schema path.
 *
 *   mydb.yaml          -> mydb.bp.json
 *   schema.linkml.yaml -> schema.linkml.bp.json
 *   weird.txt          -> weird.bp.json
 *
 * Pure (no fs / no env) so it can be unit tested directly.
 */
export function neighborPath(schemaPath: string): string {
	const lower = schemaPath.toLowerCase();
	let base = schemaPath;
	if (lower.endsWith('.yaml')) base = schemaPath.slice(0, -'.yaml'.length);
	else if (lower.endsWith('.yml')) base = schemaPath.slice(0, -'.yml'.length);
	else {
		const slash = Math.max(schemaPath.lastIndexOf('/'), schemaPath.lastIndexOf('\\'));
		const dot = schemaPath.lastIndexOf('.');
		if (dot > slash) base = schemaPath.slice(0, dot);
	}
	return `${base}.bp.json`;
}
