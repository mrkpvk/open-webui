/**
 * N-gram repetition detection utility.
 *
 * Used for the post-generation "no_repeat_ngram_size" approximation.
 * Ollama has no native equivalent — this runs client-side on the completed
 * response text and signals when exact repeated word n-grams are found.
 *
 * Note: this is an approximation of the generation-time constraint present in
 * Hugging Face Transformers. It detects repetition after the fact rather than
 * preventing it during beam search / sampling.
 */

/**
 * Returns the first repeated n-gram found in `text`, or null if none.
 *
 * @param text  The model response to inspect.
 * @param n     N-gram size (must be >= 2 to be meaningful).
 * @returns     The repeated n-gram string, or null.
 */
export function detectNgramRepetition(text: string, n: number): string | null {
	if (n < 2 || !text) return null;

	// Tokenise on whitespace; strip punctuation so "hello," and "hello" are the same token.
	const words = text
		.toLowerCase()
		.replace(/[^\w\s]/g, ' ')
		.split(/\s+/)
		.filter(Boolean);

	if (words.length < n * 2) return null;

	const seen = new Set<string>();
	for (let i = 0; i <= words.length - n; i++) {
		const ngram = words.slice(i, i + n).join(' ');
		if (seen.has(ngram)) return ngram;
		seen.add(ngram);
	}
	return null;
}
