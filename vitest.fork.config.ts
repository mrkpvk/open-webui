import { fileURLToPath } from 'node:url';

// Fork utilities should run without loading the application build plugins.
export default {
	resolve: { alias: { $lib: fileURLToPath(new URL('./src/lib', import.meta.url)) } },
	test: {
		include: [
			'src/lib/utils/history.test.ts',
			'src/lib/utils/benchmarkDataset.test.ts',
			'src/lib/utils/rawContext.test.ts',
			'src/lib/utils/messageParams.test.ts',
			'src/lib/utils/ngram.test.ts'
		],
		environment: 'node'
	}
};
