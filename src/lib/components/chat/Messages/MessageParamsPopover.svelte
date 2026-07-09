<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { settings } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import AdvancedParams from '$lib/components/chat/Settings/Advanced/AdvancedParams.svelte';

	const i18n = getContext('i18n');

	// The message object from history (for pre-filling existing overrides)
	export let message: Record<string, any> = {};
	// Chat-level param defaults (the 'params' variable in Chat.svelte)
	export let chatParams: Record<string, any> = {};
	// Callback: called with the new paramsOverride object (or null to clear)
	export let onSave: (params: Record<string, any> | null) => void = () => {};

	let show = false;
	let showPreview = false;
	let panelEl: HTMLDivElement;

	// Local editable copy — starts as the existing override (or empty = all null = use defaults)
	let localParams: Record<string, any> = {};
	$: {
		localParams = structuredClone(message?.paramsOverride ?? {});
	}

	// Effective = global settings merged with chat-level params merged with this message's overrides
	// (only non-null override values participate)
	$: effectiveParams = Object.fromEntries(
		Object.entries({
			...($settings?.params ?? {}),
			...chatParams,
			...Object.fromEntries(Object.entries(localParams).filter(([, v]) => v !== null))
		}).filter(([, v]) => v !== null && v !== undefined)
	);

	// Whether any override is actually set on this message
	$: hasOverride =
		message?.paramsOverride && Object.values(message.paramsOverride).some((v) => v !== null);

	const handleParamChange = (newParams: Record<string, any>) => {
		localParams = newParams;
		const overrides = Object.fromEntries(
			Object.entries(newParams).filter(([, v]) => v !== null && v !== undefined)
		);
		onSave(Object.keys(overrides).length > 0 ? overrides : null);
	};

	const clearOverride = () => {
		localParams = {};
		onSave(null);
	};

	const handleClickOutside = (e: MouseEvent) => {
		if (show && panelEl && !panelEl.contains(e.target as Node)) {
			show = false;
		}
	};
</script>

<svelte:window on:mousedown={handleClickOutside} />

<!-- Trigger button -->
<Tooltip content={$i18n.t('Message Parameters')} placement="bottom">
	<button
		type="button"
		aria-label={$i18n.t('Message Parameters')}
		class="invisible group-hover:visible p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition relative"
		class:!visible={show || hasOverride}
		class:text-blue-500={hasOverride}
		class:dark:text-blue-400={hasOverride}
		on:click|stopPropagation={() => {
			show = !show;
		}}
	>
		<!-- Sliders / adjustments icon -->
		<svg
			xmlns="http://www.w3.org/2000/svg"
			fill="none"
			viewBox="0 0 24 24"
			stroke-width="2"
			stroke="currentColor"
			class="w-4 h-4"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75"
			/>
		</svg>
	</button>
</Tooltip>

{#if show}
	<!-- Popover panel — positioned relative to its container (Message row) -->
	<div
		bind:this={panelEl}
		class="absolute z-50 right-0 mt-1 w-80 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-850 shadow-lg overflow-hidden"
		style="top: 2rem;"
		on:mousedown|stopPropagation
	>
		<!-- Header -->
		<div
			class="flex items-center justify-between px-3 py-2 border-b border-gray-100 dark:border-gray-700"
		>
			<span class="text-xs font-semibold text-gray-700 dark:text-gray-200">
				{$i18n.t('Per-message Parameters')}
			</span>
			<div class="flex items-center gap-1">
				{#if hasOverride}
					<button
						type="button"
						class="text-[10px] text-red-500 hover:text-red-600 transition px-1"
						on:click={clearOverride}
					>
						{$i18n.t('Clear')}
					</button>
				{/if}
				<button
					type="button"
					class="p-0.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
					on:click={() => (show = false)}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="w-3.5 h-3.5"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>

		<!-- Hint -->
		<div class="px-3 pt-2 pb-1 text-[10px] text-gray-400 dark:text-gray-500">
			{$i18n.t(
				'Overrides apply only to the next generation that uses this message as context. Null values fall back to global defaults.'
			)}
		</div>

		<!-- Params editor (scrollable) -->
		<div class="px-3 pb-2 max-h-72 overflow-y-auto">
			<AdvancedParams
				params={localParams}
				onChange={handleParamChange}
			/>
		</div>

		<!-- Request Preview toggle -->
		<div class="border-t border-gray-100 dark:border-gray-700">
			<button
				type="button"
				class="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
				on:click={() => (showPreview = !showPreview)}
			>
				<span class="font-medium">{$i18n.t('Resolved Parameters Preview')}</span>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-3.5 h-3.5 transition-transform {showPreview ? 'rotate-180' : ''}"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
				</svg>
			</button>

			{#if showPreview}
				<div class="px-3 pb-3">
					<p class="text-[10px] text-gray-400 dark:text-gray-500 mb-1">
						{$i18n.t(
							'Effective params for the next request from this message (global defaults → chat params → this override):'
						)}
					</p>
					<pre
						class="text-[10px] bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-auto max-h-40 text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-all"
					>{JSON.stringify(Object.keys(effectiveParams).length > 0 ? effectiveParams : { note: 'all defaults' }, null, 2)}</pre>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	/* Ensure the button container is relatively positioned so the popover anchors correctly */
</style>
