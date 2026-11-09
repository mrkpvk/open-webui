export type MessageParams = Record<string, any>;

/** Null means inherit; explicit zero, false and empty lists are overrides. */
export const resolveMessageParams = (
	...layers: (MessageParams | null | undefined)[]
): MessageParams =>
	Object.assign(
		{},
		...layers.map((layer) =>
			Object.fromEntries(Object.entries(layer ?? {}).filter(([, value]) => value != null))
		)
	);

export const normalizeStopTokens = (stop: unknown): string[] | undefined => {
	if (stop == null) return undefined;
	// Lists already contain literal sequences; whitespace, commas and percent
	// escapes can be intentional parts of a stop token.
	if (Array.isArray(stop)) {
		return stop.filter((token): token is string => typeof token === 'string' && token.length > 0);
	}
	const tokens = typeof stop === 'string' ? stop.split(',') : [];
	return tokens
		.filter((token): token is string => typeof token === 'string' && token.trim().length > 0)
		.map((token) => {
			let decoded = token.trim();
			try {
				decoded = JSON.parse(`"${decoded.replace(/"/g, '\\"')}"`);
			} catch {
				// A literal backslash need not be a JSON escape.
			}
			try {
				return decodeURIComponent(decoded);
			} catch {
				return decoded;
			}
		});
};
