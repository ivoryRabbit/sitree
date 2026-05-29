import { defineConfig } from 'vitest/config';

// Unit tests target pure TS modules (e.g. the cytoscape adapter), so no
// SvelteKit plugin is needed here — keeping it out also avoids the vite/vitest
// plugin-type conflict under vite 8.
export default defineConfig({
	test: {
		environment: 'node',
		include: ['src/**/*.{test,spec}.{js,ts}']
	}
});
