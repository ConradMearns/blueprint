# Canvas equivalence fixtures

These fixtures verify that LinkML's **slots and attributes are interchangeable**,
including when slots are **defined in a separate file and imported** — all of
them must build the _same canvas_ as the attribute-based ecommerce schema.

## The baseline

`ecommerce.canvas.json` is the **known-good canvas**, generated from the
attribute-based reference schema at `src/lib/examples/ecommerce.linkml.yaml`.
It's an order-independent fingerprint (see `../fingerprint.ts`): the tables and
their columns, the foreign-key edges, and any validation problems — i.e.
everything the canvas paints, minus positions.

Regenerate it only if the reference schema itself changes:

```bash
bun .gen-fixture.mjs   # (see git history for the one-off generator)
```

## The variants you add

Create each file below in this directory. Its test in
`../canvas-equivalence.spec.ts` is **skipped until the file exists**, then
asserts `canvasFingerprint(parse(file)) === ecommerce.canvas.json`. Because the
fingerprint is sorted by name, declaration order doesn't matter — only that the
tables, columns (name/type/pk/fk/required/multivalued), and FK edges match.

| File                               | What it should demonstrate                                                                                                                                                       |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ecommerce.slots.yaml`             | Single file. Top-level `slots:` referenced by each class via `slots: [...]` (use `slot_usage` for per-class overrides like identifiers/ranges). No `attributes:`, no `imports:`. |
| `ecommerce.attributes-import.yaml` | Uses `imports:` to pull class definitions (written with `attributes:`) from a sibling file. Proves imports work for attribute-based definitions.                                 |
| `ecommerce.slots-import.yaml`      | The headline case: `imports:` a sibling file that defines top-level `slots:`; the classes here reference those imported slots via `slots: [...]`.                                |

### Notes for the import variants

- `imports:` entries are resolved **relative to the importing file**. Put the
  imported file alongside these fixtures and name it in `imports:` _without_ the
  extension, e.g.:

  ```yaml
  # ecommerce.slots-import.yaml
  imports:
    - ecommerce.slots-import.defs # → ecommerce.slots-import.defs.yaml
  ```

- CURIE-style imports (e.g. `linkml:types`) are ignored — those types are
  builtins to us, so you can keep or drop them freely.
- The importing schema wins on name conflicts; imported definitions fill in the
  rest.
- To match the baseline, remember `id` must stay `identifier: true` (the primary
  key) and the relationship slots (`customer`, `order`, `product`, `parent`,
  `ship_to`, `category`) must keep their class ranges.

Once the files are in place, run:

```bash
bun test
```
