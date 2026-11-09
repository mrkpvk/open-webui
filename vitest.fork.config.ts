// Pure fork utilities should run without loading the application build plugins.
export default {
	test: {
		include: [
			'src/lib/utils/benchmarkDataset.test.ts',
			'src/lib/utils/rawContext.test.ts',
			'src/lib/utils/messageParams.test.ts',
			'src/lib/utils/ngram.test.ts'
		],
		environment: 'node'
	}
};
