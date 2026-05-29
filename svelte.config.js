import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// adapter-node produces a standalone server (build/index.js) that the `bp`
		// CLI runs, so the app can read the target schema and write the layout
		// neighbor file from the local filesystem.
		adapter: adapter()
	}
};

export default config;
