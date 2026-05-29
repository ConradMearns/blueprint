<script lang="ts">
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

	import exampleYaml from '$lib/examples/ecommerce.linkml.yaml?raw';

	const nodeTypes = { table: TableNode };

	let yamlText = $state(exampleYaml);
	let nodes = $state.raw<TableNodeT[]>([]);
	let edges = $state.raw<Edge[]>([]);
	let schemaName = $state('schema');
	let classCount = $state(0);
	let fkCount = $state(0);
	let error = $state<string | null>(null);
	let panelOpen = $state(true);

	/** Re-parse the LinkML and rebuild the canvas, preserving any saved positions. */
	function rebuild(text: string) {
		try {
			const schema = parseLinkML(text);
			const layout = autoLayout(schema, loadLayout(schema.name));
			const flow = schemaToFlow(schema, layout);
			schemaName = schema.name;
			classCount = schema.classes.length;
			fkCount = schema.foreignKeys.length;
			nodes = flow.nodes;
			edges = flow.edges;
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	/** Snapshot current node positions into the separate layout file. */
	function persist() {
		const layout: LayoutMap = {};
		for (const n of nodes) layout[n.id] = { x: n.position.x, y: n.position.y };
		saveLayout(schemaName, layout);
	}

	function resetLayout() {
		clearLayout(schemaName);
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
		const layout: LayoutMap = {};
		for (const n of nodes) layout[n.id] = { x: n.position.x, y: n.position.y };
		download(`${schemaName}.layout.json`, JSON.stringify(layout, null, 2), 'application/json');
	}

	async function onFile(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (file) yamlText = await file.text();
	}

	// Debounced live re-parse — runs in the browser after mount.
	$effect(() => {
		const text = yamlText;
		const t = setTimeout(() => rebuild(text), 250);
		return () => clearTimeout(t);
	});
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
			<p class="sub">LinkML → ER canvas. Edit the schema; drag tables to lay them out.</p>

			<div class="stats">
				<span><strong>{classCount}</strong> classes</span>
				<span><strong>{fkCount}</strong> relations</span>
			</div>

			<div class="actions">
				<label class="file-btn">
					Load .yaml
					<input type="file" accept=".yaml,.yml,.txt" onchange={onFile} />
				</label>
				<button onclick={() => download(`${schemaName}.linkml.yaml`, yamlText, 'text/yaml')}>
					Save schema
				</button>
				<button onclick={exportLayout}>Export layout</button>
				<button onclick={resetLayout}>Reset layout</button>
			</div>

			{#if error}
				<div class="error" role="alert">{error}</div>
			{/if}

			<textarea bind:value={yamlText} spellcheck="false"></textarea>
		{/if}
	</aside>

	<main>
		<SvelteFlow bind:nodes bind:edges {nodeTypes} fitView minZoom={0.1} onnodedragstop={persist}>
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

	.stats {
		display: flex;
		gap: 14px;
		font-size: 12px;
		color: #cbd5e1;
	}
	.stats strong {
		color: #f8fafc;
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
