<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { SvelteFlow, Background, Controls, MiniMap, Panel, type Edge } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';

	import TableNode from '$lib/components/TableNode.svelte';
	import { parseLinkML } from '$lib/linkml/parse';
	import {
		schemaToFlow,
		autoLayout,
		type TableNode as TableNodeT,
		type LayoutMap
	} from '$lib/linkml/toFlow';
	import { loadLayout, saveLayout, clearLayout } from '$lib/layout/store';
	import type { SchemaProblem } from '$lib/linkml/types';

	import exampleYaml from '$lib/examples/ecommerce.linkml.yaml?raw';

	const nodeTypes = { table: TableNode };

	let yamlText = $state(exampleYaml);
	let nodes = $state.raw<TableNodeT[]>([]);
	let edges = $state.raw<Edge[]>([]);
	let schemaName = $state('schema');
	let classCount = $state(0);
	let fkCount = $state(0);
	let problems = $state<SchemaProblem[]>([]);
	let error = $state<string | null>(null);
	let panelOpen = $state(true);
	let ready = $state(false);

	// File-backed (bp CLI) state. In browser mode all of these stay falsy.
	let serverBacked = $state(false);
	let fileName = $state<string | null>(null);
	let layoutName = $state<string | null>(null);
	let saveState = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let watching = $state(false);
	let source: EventSource | null = null;

	// Working positions, seeded from disk or localStorage and updated on drag.
	let layout: LayoutMap = {};
	let lastSavedYaml = '';

	const postJSON = (url: string, body: unknown) =>
		fetch(url, {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify(body)
		});

	/** Re-parse the LinkML and rebuild the canvas, preserving current positions. */
	function rebuild(text: string) {
		try {
			const schema = parseLinkML(text);
			layout = autoLayout(schema, layout);
			const flow = schemaToFlow(schema, layout);
			schemaName = schema.name;
			classCount = schema.classes.length;
			fkCount = schema.foreignKeys.length;
			problems = schema.problems;
			nodes = flow.nodes;
			edges = flow.edges;
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	function snapshot(): LayoutMap {
		const next: LayoutMap = {};
		for (const n of nodes) next[n.id] = { x: n.position.x, y: n.position.y };
		return next;
	}

	/** Persist positions: to the .bp.json neighbor on disk, or localStorage in browser mode. */
	async function persistLayout() {
		layout = snapshot();
		if (serverBacked) {
			saveState = 'saving';
			try {
				await postJSON('/api/layout', { layout });
				saveState = 'saved';
			} catch {
				saveState = 'error';
			}
		} else {
			saveLayout(schemaName, layout);
		}
	}

	/** Persist schema text back to the source file (file-backed mode only). */
	async function persistSchema(text: string) {
		saveState = 'saving';
		try {
			await postJSON('/api/schema', { yaml: text });
			lastSavedYaml = text;
			saveState = 'saved';
		} catch {
			saveState = 'error';
		}
	}

	async function resetLayout() {
		layout = {};
		if (serverBacked) await postJSON('/api/layout', { layout: {} }).catch(() => {});
		else clearLayout(schemaName);
		rebuild(yamlText);
	}

	function download(filename: string, content: string, mime = 'text/plain') {
		const url = URL.createObjectURL(new Blob([content], { type: mime }));
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		a.click();
		URL.revokeObjectURL(url);
	}

	function exportLayout() {
		download(`${schemaName}.bp.json`, JSON.stringify(snapshot(), null, 2), 'application/json');
	}

	async function onFile(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (file) yamlText = await file.text();
	}

	/** Apply a change the server detected on disk, without echoing it back. */
	function applyExternal(event: { type: string; yaml?: string; layout?: LayoutMap }) {
		if (event.type === 'schema' && typeof event.yaml === 'string') {
			// Don't clobber unsaved local edits; otherwise adopt the on-disk version.
			if (yamlText === lastSavedYaml && event.yaml !== yamlText) {
				lastSavedYaml = event.yaml; // mark in-sync so the autosave effect skips it
				yamlText = event.yaml; // triggers the debounced rebuild
			}
		} else if (event.type === 'layout' && event.layout) {
			layout = event.layout;
			rebuild(yamlText);
		}
	}

	/** Subscribe to on-disk changes via Server-Sent Events (file-backed mode). */
	function startWatching() {
		source = new EventSource('/api/watch');
		source.onopen = () => (watching = true);
		source.onerror = () => (watching = false); // EventSource auto-reconnects
		source.onmessage = (ev) => {
			try {
				applyExternal(JSON.parse(ev.data));
			} catch {
				// ignore malformed events
			}
		};
	}

	onMount(async () => {
		try {
			const res = await fetch('/api/schema');
			const data = await res.json();
			if (data.serverBacked) {
				serverBacked = true;
				fileName = data.fileName;
				layoutName = data.layoutName;
				if (typeof data.yaml === 'string' && data.yaml.length) yamlText = data.yaml;
				layout = (data.layout as LayoutMap) ?? {};
			}
		} catch {
			// No server (static browser build) — fall through to browser mode.
		}

		if (!serverBacked) {
			try {
				layout = loadLayout(parseLinkML(yamlText).name);
			} catch {
				layout = {};
			}
		}

		lastSavedYaml = yamlText;
		rebuild(yamlText);
		ready = true;

		if (serverBacked) startWatching();
	});

	onDestroy(() => source?.close());

	// Debounced live re-parse; in file-backed mode also autosave valid edits to disk.
	$effect(() => {
		const text = yamlText;
		if (!ready) return;
		if (serverBacked && text !== lastSavedYaml) saveState = 'idle';
		const t = setTimeout(() => {
			rebuild(text);
			if (serverBacked && error === null && text !== lastSavedYaml) persistSchema(text);
		}, 400);
		return () => clearTimeout(t);
	});

	const saveLabel = $derived(
		{ idle: '', saving: 'saving…', saved: 'saved ✓', error: 'save failed' }[saveState]
	);
</script>

<div class="app">
	<aside class:open={panelOpen}>
		<div class="panel-head">
			<h1>blueprint</h1>
			<button class="ghost" onclick={() => (panelOpen = !panelOpen)} title="Toggle panel">
				{panelOpen ? '◀' : '▶'}
			</button>
		</div>

		{#if panelOpen}
			{#if serverBacked}
				<div class="file">
					<span class="path" title={fileName ?? ''}>
						<span
							class="watch-dot"
							class:live={watching}
							title={watching ? 'watching for changes' : 'not watching'}
						></span>
						📄 {fileName}
					</span>
					<span class="layout-path" title={layoutName ?? ''}>↳ {layoutName}</span>
					<span class="save-state {saveState}">{saveLabel}</span>
				</div>
			{:else}
				<p class="sub">Browser mode — drag tables; layout is saved to localStorage.</p>
			{/if}

			<div class="stats">
				<span><strong>{classCount}</strong> classes</span>
				<span><strong>{fkCount}</strong> relations</span>
				<span class:bad={problems.length > 0}>
					<strong>{problems.length}</strong> issues
				</span>
			</div>

			{#if problems.length}
				<ul class="problems">
					{#each problems as p (p.className + '.' + p.slot)}
						<li title={p.message}>
							⚠️ <code>{p.className}.{p.slot}</code> — {p.message}
						</li>
					{/each}
				</ul>
			{/if}

			<div class="actions">
				{#if serverBacked}
					<button onclick={resetLayout}>Reset layout</button>
					<button onclick={exportLayout}>Export layout copy</button>
				{:else}
					<label class="file-btn">
						Load .yaml
						<input type="file" accept=".yaml,.yml,.txt" onchange={onFile} />
					</label>
					<button onclick={() => download(`${schemaName}.linkml.yaml`, yamlText, 'text/yaml')}>
						Save schema
					</button>
					<button onclick={exportLayout}>Export layout</button>
					<button onclick={resetLayout}>Reset layout</button>
				{/if}
			</div>

			{#if error}
				<div class="error" role="alert">{error}</div>
			{/if}

			<textarea bind:value={yamlText} spellcheck="false"></textarea>
		{/if}
	</aside>

	<main>
		{#if ready}
			<SvelteFlow
				bind:nodes
				bind:edges
				{nodeTypes}
				fitView
				minZoom={0.1}
				onnodedragstop={persistLayout}
			>
				<Background />
				<Controls />
				<MiniMap pannable zoomable />
				<Panel position="top-right">
					<div class="legend">
						<span><span class="dot pk"></span> primary key</span>
						<span><span class="dot fk"></span> foreign key</span>
					</div>
				</Panel>
			</SvelteFlow>
		{/if}
	</main>
</div>

<style>
	:global(html, body) {
		margin: 0;
		height: 100%;
	}
	:global(body) {
		font-family:
			ui-sans-serif,
			system-ui,
			-apple-system,
			sans-serif;
	}

	.app {
		display: flex;
		height: 100vh;
		width: 100vw;
		overflow: hidden;
	}

	aside {
		display: flex;
		flex-direction: column;
		gap: 10px;
		width: 360px;
		min-width: 360px;
		padding: 14px;
		box-sizing: border-box;
		background: #0f172a;
		color: #e2e8f0;
		transition:
			width 0.15s ease,
			min-width 0.15s ease;
	}
	aside:not(.open) {
		width: 48px;
		min-width: 48px;
		padding: 14px 8px;
	}

	.panel-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	h1 {
		font-size: 18px;
		margin: 0;
		letter-spacing: 0.03em;
	}
	aside:not(.open) h1 {
		display: none;
	}
	.ghost {
		background: transparent;
		color: #94a3b8;
		border: 1px solid #334155;
		border-radius: 6px;
		cursor: pointer;
		padding: 4px 8px;
	}
	.sub {
		font-size: 12px;
		color: #94a3b8;
		margin: 0;
	}

	.file {
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-size: 12px;
		background: #020617;
		border: 1px solid #1e293b;
		border-radius: 6px;
		padding: 8px 10px;
	}
	.file .path {
		display: flex;
		align-items: center;
		gap: 6px;
		font-weight: 600;
		color: #f8fafc;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.watch-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #475569;
		flex: none;
	}
	.watch-dot.live {
		background: #4ade80;
		box-shadow: 0 0 0 2px rgba(74, 222, 128, 0.25);
	}
	.file .layout-path {
		color: #64748b;
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 11px;
	}
	.save-state {
		font-size: 11px;
		min-height: 13px;
		color: #94a3b8;
	}
	.save-state.saved {
		color: #4ade80;
	}
	.save-state.error {
		color: #f87171;
	}

	.stats {
		display: flex;
		gap: 14px;
		font-size: 12px;
		color: #cbd5e1;
	}
	.stats strong {
		color: #f8fafc;
	}
	.stats .bad strong {
		color: #f87171;
	}

	.problems {
		list-style: none;
		margin: 0;
		padding: 8px 10px;
		display: flex;
		flex-direction: column;
		gap: 4px;
		max-height: 140px;
		overflow-y: auto;
		font-size: 11px;
		line-height: 1.4;
		background: #450a0a;
		color: #fecaca;
		border: 1px solid #7f1d1d;
		border-radius: 6px;
	}
	.problems code {
		color: #fca5a5;
		font-family: ui-monospace, SFMono-Regular, monospace;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.actions button,
	.file-btn {
		font-size: 12px;
		padding: 6px 10px;
		border-radius: 6px;
		border: 1px solid #334155;
		background: #1e293b;
		color: #e2e8f0;
		cursor: pointer;
	}
	.actions button:hover,
	.file-btn:hover {
		background: #334155;
	}
	.file-btn input {
		display: none;
	}

	.error {
		font-size: 12px;
		background: #7f1d1d;
		color: #fecaca;
		padding: 8px 10px;
		border-radius: 6px;
		white-space: pre-wrap;
	}

	textarea {
		flex: 1;
		resize: none;
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 12px;
		line-height: 1.5;
		padding: 10px;
		border-radius: 8px;
		border: 1px solid #334155;
		background: #020617;
		color: #e2e8f0;
		tab-size: 2;
	}

	main {
		flex: 1;
		height: 100%;
	}

	.legend {
		display: flex;
		gap: 12px;
		font-size: 11px;
		background: #ffffff;
		border: 1px solid #c7ccd6;
		border-radius: 6px;
		padding: 6px 10px;
		color: #334155;
	}
	.legend span {
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.dot {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		display: inline-block;
	}
	.dot.pk {
		background: #fcd34d;
	}
	.dot.fk {
		background: #93c5fd;
	}
</style>
