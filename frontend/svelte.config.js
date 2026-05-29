import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// Static SPA build. The graph JSON is loaded at runtime from the backend
		// (`GET /api/graph` served by `sitree view`), so we render a single client
		// shell and fall back to index.html for client-side routing.
		adapter: adapter({ fallback: 'index.html' })
	}
};

export default config;
