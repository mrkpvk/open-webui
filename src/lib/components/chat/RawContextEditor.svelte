<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as I18n } from 'i18next';
	import { applyContextPath, editableContextPath, type EditableContextMessage } from '$lib/utils/rawContext';
	import { toast } from 'svelte-sonner';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext<Writable<I18n>>('i18n');

	export let history: { currentId: string | null; messages: Record<string, any> };
	export let chatId: string;
	// Called with updated history after Apply — parent saves it
	export let onApply: (newHistory: typeof history) => void | Promise<void> = () => {};
	// Called when user cancels/closes without saving
	export let onClose: () => void = () => {};

	// Roles available for a message
	const ROLES = ['user', 'assistant', 'system'] as const;
	type Role = (typeof ROLES)[number];

	type EditableMessage = EditableContextMessage;

	let editableMessages: EditableMessage[] = editableContextPath(history);
	let saving = false;

	// Paste transcript mode
	let showPasteModal = false;
	let pasteText = '';

	const addMessage = (afterIdx: number) => {
		const newMsg: EditableMessage = {
			id: crypto.randomUUID(),
			role: 'user',
			content: ''
		};
		editableMessages = [
			...editableMessages.slice(0, afterIdx + 1),
			newMsg,
			...editableMessages.slice(afterIdx + 1)
		];
	};

	const removeMessage = (idx: number) => {
		if (editableMessages.length <= 1) {
			toast.error($i18n.t('Cannot remove the last message'));
			return;
		}
		editableMessages = editableMessages.filter((_, i) => i !== idx);
	};

	const moveUp = (idx: number) => {
		if (idx === 0) return;
		const arr = [...editableMessages];
		[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]];
		editableMessages = arr;
	};

	const moveDown = (idx: number) => {
		if (idx === editableMessages.length - 1) return;
		const arr = [...editableMessages];
		[arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]];
		editableMessages = arr;
	};

	const cycleRole = (idx: number) => {
		const current = editableMessages[idx].role;
		const nextIdx = (ROLES.indexOf(current) + 1) % ROLES.length;
		editableMessages[idx] = { ...editableMessages[idx], role: ROLES[nextIdx] };
		editableMessages = [...editableMessages];
	};

	const applyChanges = async () => {
		if (editableMessages.length === 0) {
			toast.error($i18n.t('Cannot apply empty message list'));
			return;
		}

		if (saving) return;
		saving = true;
		try {
			await onApply(applyContextPath(history, editableMessages));
		} catch (error) {
			toast.error($i18n.t('Could not save context changes'));
		} finally {
			saving = false;
		}
	};

	// Parse pasted transcript
	// Supported format:
	//   User: message text
	//   Assistant: message text
	//   System: message text
	// Multi-line messages: lines not starting with a role prefix continue the previous message.
	const parsePaste = () => {
		if (!pasteText.trim()) return;

		const rolePattern = /^(User|Assistant|System):\s*/i;
		const lines = pasteText.split('\n');
		const parsed: EditableMessage[] = [];
		let current: EditableMessage | null = null;

		for (const line of lines) {
			const match = line.match(rolePattern);
			if (match) {
				if (current) parsed.push(current);
				const roleName = match[1].toLowerCase() as Role;
				const role: Role = roleName === 'assistant' ? 'assistant' : roleName === 'system' ? 'system' : 'user';
				current = {
					id: crypto.randomUUID(),
					role,
					content: line.replace(rolePattern, '').trimEnd()
				};
			} else if (current) {
				current.content += '\n' + line;
			}
		}
		if (current) parsed.push(current);

		if (parsed.length === 0) {
			toast.error($i18n.t('Could not parse any messages. Use "User: ...", "Assistant: ...", or "System: ..." prefixes.'));
			return;
		}

		// Trim trailing newlines from each content
		parsed.forEach((m) => (m.content = m.content.trimEnd()));
		editableMessages = parsed;
		showPasteModal = false;
		pasteText = '';
		toast.success($i18n.t('{n} messages loaded from transcript', { n: parsed.length }));
	};

	const roleLabel = (role: Role) => {
		return { user: 'U', assistant: 'A', system: 'S' }[role] ?? role[0].toUpperCase();
	};

	const roleColor = (role: Role) => {
		return {
			user: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
			assistant: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
			system: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300'
		}[role];
	};
</script>

<!-- Full-height overlay replacing the normal chat view -->
<div class="flex flex-col h-full w-full">
	<!-- Header bar -->
	<div
		class="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0"
	>
		<div class="flex items-center gap-2">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="2"
				stroke="currentColor"
				class="w-4 h-4 text-gray-500"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12"
				/>
			</svg>
			<span class="text-sm font-semibold text-gray-800 dark:text-gray-100">
				{$i18n.t('Raw Context Editor')}
			</span>
			<span class="text-xs text-gray-400 dark:text-gray-500">
				{editableMessages.length}
				{$i18n.t('messages')}
			</span>
		</div>

		<div class="flex items-center gap-2">
			<Tooltip content={$i18n.t('Paste transcript')} placement="bottom">
				<button
					type="button"
					class="flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => (showPasteModal = true)}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="w-3.5 h-3.5"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z"
						/>
					</svg>
					{$i18n.t('Paste')}
				</button>
			</Tooltip>

			<button
				type="button"
				class="text-xs px-3 py-1 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium transition"
				on:click={applyChanges}
				disabled={saving}
			>
				{$i18n.t('Apply')}
			</button>

			<button
				type="button"
				class="text-xs px-3 py-1 rounded-md border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
				on:click={onClose}
			>
				{$i18n.t('Cancel')}
			</button>
		</div>
	</div>

	<!-- Message list -->
	<div class="flex-1 overflow-y-auto px-4 py-3 space-y-2">
		{#each editableMessages as msg, idx (msg.id)}
			<div class="flex gap-2 group/row items-start">
				<!-- Role badge (click to cycle) -->
				<Tooltip content={$i18n.t('Click to cycle role: user → assistant → system')} placement="right">
					<button
						type="button"
						class="mt-1.5 shrink-0 w-7 h-7 rounded-md text-xs font-bold flex items-center justify-center {roleColor(msg.role)} transition hover:opacity-80"
						on:click={() => cycleRole(idx)}
					>
						{roleLabel(msg.role)}
					</button>
				</Tooltip>

				<!-- Text area -->
				<textarea
					class="flex-1 min-h-[60px] resize-y rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-800 dark:text-gray-100 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-600 transition font-mono"
					bind:value={msg.content}
					placeholder="{msg.role === 'system' ? $i18n.t('System instruction…') : msg.role === 'assistant' ? $i18n.t('Assistant response…') : $i18n.t('User message…')}"
				/>

				<!-- Row actions (visible on hover) -->
				<div
					class="shrink-0 flex flex-col gap-0.5 opacity-0 group-hover/row:opacity-100 transition mt-1"
				>
					<Tooltip content={$i18n.t('Move up')} placement="left">
						<button
							type="button"
							class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 disabled:opacity-20"
							disabled={idx === 0}
							on:click={() => moveUp(idx)}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="w-3.5 h-3.5"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="m4.5 15.75 7.5-7.5 7.5 7.5"
								/>
							</svg>
						</button>
					</Tooltip>

					<Tooltip content={$i18n.t('Move down')} placement="left">
						<button
							type="button"
							class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 disabled:opacity-20"
							disabled={idx === editableMessages.length - 1}
							on:click={() => moveDown(idx)}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="w-3.5 h-3.5"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="m19.5 8.25-7.5 7.5-7.5-7.5"
								/>
							</svg>
						</button>
					</Tooltip>

					<Tooltip content={$i18n.t('Delete message')} placement="left">
						<button
							type="button"
							class="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 transition"
							on:click={() => removeMessage(idx)}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="w-3.5 h-3.5"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
								/>
							</svg>
						</button>
					</Tooltip>
				</div>
			</div>

			<!-- Insert below button -->
			<div class="flex justify-center opacity-0 hover:opacity-100 transition -my-1">
				<button
					type="button"
					class="text-[10px] flex items-center gap-1 px-2 py-0.5 rounded border border-dashed border-gray-300 dark:border-gray-600 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:border-gray-400 transition"
					on:click={() => addMessage(idx)}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="w-3 h-3"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
					</svg>
					{$i18n.t('Insert below')}
				</button>
			</div>
		{/each}

		<!-- Add message at bottom -->
		<div class="flex justify-center pt-1">
			<button
				type="button"
				class="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-blue-400 hover:text-blue-500 dark:hover:text-blue-400 transition"
				on:click={() => addMessage(editableMessages.length - 1)}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-3.5 h-3.5"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
				</svg>
				{$i18n.t('Add message')}
			</button>
		</div>
	</div>

	<!-- Footer hint -->
	<div
		class="shrink-0 px-4 py-2 border-t border-gray-200 dark:border-gray-700 text-[10px] text-gray-400 dark:text-gray-500"
	>
		{$i18n.t(
			'Click role badge to cycle (U=user, A=assistant, S=system). Apply saves the edited path as a new branch. Original messages and other branches are preserved.'
		)}
	</div>
</div>

<!-- Paste Transcript Modal -->
{#if showPasteModal}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		class="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4"
		on:click|self={() => (showPasteModal = false)}
	>
		<div
			class="w-full max-w-lg bg-white dark:bg-gray-900 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden"
		>
			<div
				class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700"
			>
				<span class="font-semibold text-sm text-gray-800 dark:text-gray-100">
					{$i18n.t('Paste Transcript')}
				</span>
				<button
					type="button"
					class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
					on:click={() => (showPasteModal = false)}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="w-4 h-4"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<div class="px-4 py-3 flex-1">
				<p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
					{$i18n.t(
						'Paste a conversation. Each message starts with a role prefix on a new line. Continuation lines (no prefix) are appended to the previous message.'
					)}
				</p>
				<pre
					class="text-[10px] bg-gray-50 dark:bg-gray-800 rounded p-2 text-gray-500 dark:text-gray-400 mb-2 whitespace-pre"
				>User: Hello, how are you?
Assistant: I'm doing well, thanks!
    How can I help you today?
System: You are a helpful assistant.</pre>

				<textarea
					class="w-full h-48 resize-none rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-800 dark:text-gray-100 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
					placeholder={`User: Hello!\nAssistant: Hi there!\nSystem: You are a helpful assistant.`}
					bind:value={pasteText}
				/>
			</div>

			<div class="flex justify-end gap-2 px-4 pb-4">
				<button
					type="button"
					class="text-xs px-3 py-1.5 rounded-md border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => (showPasteModal = false)}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					type="button"
					class="text-xs px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium transition"
					on:click={parsePaste}
				>
					{$i18n.t('Load')}
				</button>
			</div>
		</div>
	</div>
{/if}
