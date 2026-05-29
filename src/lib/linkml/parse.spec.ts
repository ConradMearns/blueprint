import { describe, it, expect } from 'vitest';
import { parseLinkML } from './parse';

const SCHEMA = `
name: shop
default_range: string
classes:
  Customer:
    attributes:
      id:
        identifier: true
        range: integer
      email:
        required: true
  Order:
    description: A purchase
    attributes:
      id:
        identifier: true
        range: integer
      customer:
        range: Customer
        required: true
      tags:
        range: string
        multivalued: true
`;

describe('parseLinkML', () => {
	const schema = parseLinkML(SCHEMA);

	it('reads the schema name', () => {
		expect(schema.name).toBe('shop');
	});

	it('parses all classes', () => {
		expect(schema.classes.map((c) => c.name)).toEqual(['Customer', 'Order']);
	});

	it('identifies the primary key slot', () => {
		const customer = schema.classes.find((c) => c.name === 'Customer')!;
		expect(customer.identifierSlot).toBe('id');
		expect(customer.slots.find((s) => s.name === 'id')?.identifier).toBe(true);
	});

	it('applies default_range to slots without an explicit range', () => {
		const customer = schema.classes.find((c) => c.name === 'Customer')!;
		expect(customer.slots.find((s) => s.name === 'email')?.range).toBe('string');
	});

	it('flags required and multivalued slots', () => {
		const order = schema.classes.find((c) => c.name === 'Order')!;
		const tags = order.slots.find((s) => s.name === 'tags')!;
		expect(tags.multivalued).toBe(true);
		const customer = order.slots.find((s) => s.name === 'customer')!;
		expect(customer.required).toBe(true);
	});

	it('detects a foreign key when a slot range is a class', () => {
		expect(schema.foreignKeys).toHaveLength(1);
		const fk = schema.foreignKeys[0];
		expect(fk.fromClass).toBe('Order');
		expect(fk.fromSlot).toBe('customer');
		expect(fk.toClass).toBe('Customer');
		expect(fk.toSlot).toBe('id');
	});

	it('does not treat scalar ranges as foreign keys', () => {
		const order = schema.classes.find((c) => c.name === 'Order')!;
		expect(order.slots.find((s) => s.name === 'tags')?.refClass).toBeUndefined();
	});
});

describe('parseLinkML validation', () => {
	// Order has been deleted, but OrderLine.order still points at it.
	const schema = parseLinkML(`
name: shop
classes:
  OrderLine:
    attributes:
      id: { identifier: true, range: integer }
      order: { range: Order, required: true }
      note: { range: string }
enums:
  status:
    permissible_values:
      open:
`);

	it('flags a slot whose range is an unknown class/type/enum', () => {
		const orderLine = schema.classes.find((c) => c.name === 'OrderLine')!;
		expect(orderLine.slots.find((s) => s.name === 'order')?.unresolved).toBe(true);
	});

	it('reports the broken reference as a problem', () => {
		expect(schema.problems).toHaveLength(1);
		expect(schema.problems[0]).toMatchObject({
			level: 'error',
			className: 'OrderLine',
			slot: 'order'
		});
	});

	it('does not create a foreign key for an unresolved range', () => {
		expect(schema.foreignKeys).toHaveLength(0);
	});

	it('does not flag valid builtins or enums', () => {
		const orderLine = schema.classes.find((c) => c.name === 'OrderLine')!;
		expect(orderLine.slots.find((s) => s.name === 'note')?.unresolved).toBe(false);
		expect(orderLine.slots.find((s) => s.name === 'id')?.unresolved).toBe(false);
	});
});

describe('parseLinkML inheritance', () => {
	const schema = parseLinkML(`
name: inherit
classes:
  Base:
    attributes:
      id:
        identifier: true
        range: integer
  Derived:
    is_a: Base
    attributes:
      label:
        range: string
`);

	it('inherits slots from is_a parents', () => {
		const derived = schema.classes.find((c) => c.name === 'Derived')!;
		expect(derived.slots.map((s) => s.name)).toEqual(['id', 'label']);
		expect(derived.identifierSlot).toBe('id');
	});
});

describe('parseLinkML imports', () => {
	const shared = `
slots:
  id:
    identifier: true
    range: integer
  owner:
    range: User
`;
	const main = `
name: imported
imports:
  - shared
  - linkml:types
classes:
  User:
    slots: [id]
  Widget:
    slots: [id, owner]
`;
	const schema = parseLinkML(main, {
		resolveImport: (name) => (name === 'shared' ? shared : null)
	});

	it('merges imported slots so classes can reference them', () => {
		const widget = schema.classes.find((c) => c.name === 'Widget')!;
		expect(widget.slots.map((s) => s.name)).toEqual(['id', 'owner']);
		expect(widget.identifierSlot).toBe('id');
	});

	it('detects foreign keys through imported slots', () => {
		expect(schema.foreignKeys).toEqual([
			expect.objectContaining({
				fromClass: 'Widget',
				fromSlot: 'owner',
				toClass: 'User',
				toSlot: 'id'
			})
		]);
	});

	it('skips CURIE imports without reporting problems', () => {
		// `linkml:types` resolves to null and must not break parsing.
		expect(schema.problems).toEqual([]);
	});

	it('ignores imports entirely when no resolver is supplied', () => {
		const noResolver = parseLinkML(main);
		// Without a resolver the imported `owner` slot is unknown, so Widget has
		// no `owner` column and therefore no foreign key.
		expect(noResolver.foreignKeys).toEqual([]);
	});
});
