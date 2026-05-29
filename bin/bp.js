#!/usr/bin/env node
// bp — open a LinkML schema in the blueprint ER canvas.
//
//   bp mydb.yaml            # build (first run) + serve, open the browser
//   bp mydb.yaml --port 5000
//   bp mydb.yaml --no-open
//   bp mydb.yaml --rebuild  # force a fresh production build first
//
// Layout is written to a neighbor file (mydb.bp.json) by the running app.

import { existsSync } from 'node:fs';
import { resolve, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn, spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

function help() {
	console.log(`bp — LinkML ER canvas

Usage:
  bp <schema.yaml> [options]

Options:
  -p, --port <n>   Port to serve on (default: 4321)
      --no-open    Do not open a browser
      --rebuild    Rebuild the app before serving
  -h, --help       Show this help`);
}

const argv = process.argv.slice(2);
let file = null;
let port = '4321';
let open = true;
let rebuild = false;

for (let i = 0; i < argv.length; i++) {
	const a = argv[i];
	if (a === '-h' || a === '--help') {
		help();
		process.exit(0);
	} else if (a === '-p' || a === '--port') port = argv[++i];
	else if (a === '--no-open') open = false;
	else if (a === '--rebuild') rebuild = true;
	else if (!a.startsWith('-')) file = a;
	else {
		console.error(`bp: unknown option ${a}`);
		process.exit(1);
	}
}

if (!file) {
	help();
	process.exit(1);
}

const schema = resolve(process.cwd(), file);
if (!existsSync(schema)) {
	console.error(`bp: file not found: ${schema}`);
	process.exit(1);
}

const buildEntry = resolve(root, 'build', 'index.js');
if (rebuild || !existsSync(buildEntry)) {
	console.log('bp: building app…');
	const built = spawnSync('bun', ['run', 'build'], { cwd: root, stdio: 'inherit' });
	if (built.status !== 0) {
		console.error('bp: build failed');
		process.exit(1);
	}
}

const url = `http://localhost:${port}`;
const server = spawn('node', [buildEntry], {
	cwd: root,
	stdio: 'inherit',
	env: {
		...process.env,
		HOST: '127.0.0.1',
		PORT: String(port),
		ORIGIN: url,
		BP_FILE: schema
	}
});

if (open) {
	(async () => {
		for (let i = 0; i < 100; i++) {
			try {
				await fetch(url);
				break;
			} catch {
				await new Promise((r) => setTimeout(r, 150));
			}
		}
		const cmd =
			process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
		spawn(cmd, [url], {
			stdio: 'ignore',
			detached: true,
			shell: process.platform === 'win32'
		}).unref();
		console.log(`\nbp: serving ${basename(schema)} → ${url}\n`);
	})();
}

process.on('SIGINT', () => server.kill('SIGINT'));
process.on('SIGTERM', () => server.kill('SIGTERM'));
server.on('exit', (code) => process.exit(code ?? 0));
