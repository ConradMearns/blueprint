import type { RequestHandler } from './$types';
import { schemaPath } from '$lib/server/store';
import { subscribe } from '$lib/server/watch';

/**
 * Server-Sent Events stream of on-disk changes to the schema and its layout
 * neighbor. The client (EventSource) applies them to the canvas live.
 */
export const GET: RequestHandler = ({ request }) => {
	if (!schemaPath()) return new Response('Not file-backed', { status: 409 });

	const encoder = new TextEncoder();
	let unsubscribe = () => {};

	const stream = new ReadableStream({
		start(controller) {
			controller.enqueue(encoder.encode(': connected\n\n'));
			unsubscribe = subscribe((event) => {
				try {
					controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
				} catch {
					unsubscribe();
				}
			});
			request.signal.addEventListener('abort', () => {
				unsubscribe();
				try {
					controller.close();
				} catch {
					// already closed
				}
			});
		},
		cancel() {
			unsubscribe();
		}
	});

	return new Response(stream, {
		headers: {
			'content-type': 'text/event-stream',
			'cache-control': 'no-cache',
			connection: 'keep-alive'
		}
	});
};
