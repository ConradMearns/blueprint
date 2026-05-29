<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import type { TableNodeData } from '$lib/linkml/toFlow';

	let { data }: NodeProps = $props();
	const table = $derived(data as TableNodeData);
</script>

<div class="table-node">
	<header>
		<span class="title">{table.name}</span>
		{#if table.description}
			<span class="desc" title={table.description}>{table.description}</span>
		{/if}
	</header>

	<div class="cols">
		{#each table.columns as col (col.name)}
			<div class="row" class:pk={col.pk} class:fk={col.fk} class:unresolved={col.unresolved}>
				<!-- Per-row connection points; xyflow measures their real DOM position. -->
				<Handle type="target" position={Position.Left} id={`t-${col.name}`} class="row-handle" />

				<span class="marker">
					{#if col.unresolved}⚠️{:else if col.pk}🔑{:else if col.fk}🔗{:else}&nbsp;{/if}
				</span>
				<span class="name">
					{col.name}{#if col.required}<span class="req" title="required">*</span>{/if}
				</span>
				<span class="type" title={col.unresolved ? `Unknown range "${col.type}"` : undefined}>
					{col.type}{#if col.multivalued}[]{/if}
				</span>

				<Handle type="source" position={Position.Right} id={`s-${col.name}`} class="row-handle" />
			</div>
		{/each}
	</div>
</div>

<style>
	.table-node {
		min-width: 220px;
		font-family:
			ui-sans-serif,
			system-ui,
			-apple-system,
			sans-serif;
		font-size: 12px;
		background: #ffffff;
		border: 1px solid #c7ccd6;
		border-radius: 8px;
		box-shadow: 0 2px 8px rgba(15, 23, 42, 0.12);
		overflow: hidden;
	}

	header {
		display: flex;
		flex-direction: column;
		gap: 1px;
		padding: 7px 12px;
		background: #1e293b;
		color: #f8fafc;
	}
	header .title {
		font-weight: 700;
		letter-spacing: 0.02em;
	}
	header .desc {
		font-size: 10px;
		font-weight: 400;
		color: #cbd5e1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 260px;
	}

	.cols {
		display: flex;
		flex-direction: column;
	}

	.row {
		position: relative;
		display: grid;
		grid-template-columns: 18px 1fr auto;
		align-items: center;
		gap: 8px;
		padding: 4px 12px;
		border-top: 1px solid #eef1f6;
	}
	.row.pk {
		background: #fffbeb;
	}
	.row.fk {
		background: #eff6ff;
	}
	.row.unresolved {
		background: #fef2f2;
		box-shadow: inset 3px 0 0 #dc2626;
	}
	.row.unresolved .name,
	.row.unresolved .type {
		color: #b91c1c;
	}

	.marker {
		text-align: center;
		font-size: 10px;
	}
	.name {
		font-weight: 500;
		color: #0f172a;
	}
	.row.pk .name {
		font-weight: 700;
	}
	.req {
		color: #dc2626;
		margin-left: 1px;
	}
	.type {
		color: #64748b;
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 11px;
	}

	/* Handle styling — class is forwarded to xyflow's element, so target globally. */
	:global(.row-handle) {
		width: 8px;
		height: 8px;
		background: #94a3b8;
		border: 1px solid #ffffff;
	}
	:global(.row .row-handle) {
		opacity: 0;
		transition: opacity 0.12s ease;
	}
	:global(.table-node:hover .row-handle) {
		opacity: 1;
	}
</style>
