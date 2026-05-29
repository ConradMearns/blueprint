# blueprint

An infinite-canvas **ER diagram editor driven by [LinkML](https://linkml.io/)**.

Point it at a LinkML schema and blueprint paints an entity-relationship diagram —
one table per class, columns from slots, and edges for the foreign-key
relationships implied by slots whose range is another class. Tables can be
dragged around freely on an infinite canvas powered by
[Svelte Flow](https://svelteflow.dev/).

This is the same idea as [dbml](https://dbml.dbdiagram.io/) and its canvas, with
two deliberate differences:

- **LinkML is the source of truth** for _what_ to draw — no custom DSL.
- A **separate layout file** records _where_ to draw. The schema stays clean and
  authoritative while users rearrange the canvas; positions never leak back into
  the model.

## Stack

- [SvelteKit](https://svelte.dev/docs/kit) + Svelte 5 (runes), TypeScript
- [Bun](https://bun.com/) for tooling and package management
- [`@xyflow/svelte`](https://svelteflow.dev/) (Svelte Flow) for the canvas
- [`yaml`](https://www.npmjs.com/package/yaml) to parse LinkML

## Develop

```bash
bun install
bun run dev        # http://localhost:5173
```

Edit the LinkML in the left panel and the diagram updates live. Drag tables to
arrange them — positions are saved to `localStorage` per schema. Use the panel
buttons to load a `.yaml` file, export the schema, export the layout JSON, or
reset the layout.

## Quality gates

```bash
bun test           # unit tests (Vitest)
bun run check      # type-check (svelte-check)
bun run lint       # prettier + eslint
bun run build      # production build
```

## How it works

| Concern                        | Module                                |
| ------------------------------ | ------------------------------------- |
| Parse LinkML → ER model        | `src/lib/linkml/parse.ts`             |
| ER model types                 | `src/lib/linkml/types.ts`             |
| Model + layout → flow graph    | `src/lib/linkml/toFlow.ts`            |
| Layout persistence (the where) | `src/lib/layout/store.ts`             |
| Table node rendering           | `src/lib/components/TableNode.svelte` |
| Canvas + editor                | `src/routes/+page.svelte`             |

### LinkML subset supported

`classes` with inline `attributes` and/or referenced top-level `slots`,
reusable `slots`, `slot_usage` overrides, and `is_a` / `mixins` inheritance.
A slot is treated as a **foreign key** when its `range` matches another class
name; `identifier: true` (or `key: true`) marks the **primary key**.

## Issue tracking

This repo uses [Seeds](https://github.com/jayminwest/seeds) (`sd`) for git-native
issue tracking. Run `sd prime` for the workflow, `sd ready` to find work.
