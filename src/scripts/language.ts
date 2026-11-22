type Mode = 'en' | 'ko' | 'auto';
type LanguagePair = { sourceLanguage: string; targetLanguage: string };
type TranslatorSession = {
	translate(text: string, options: { signal: AbortSignal }): Promise<string>;
	destroy(): void;
};
type BrowserTranslator = {
	availability(pair: LanguagePair): Promise<'available' | 'downloadable' | 'downloading' | 'unavailable'>;
	create(options: LanguagePair & { signal: AbortSignal }): Promise<TranslatorSession>;
};

function savedMode(): Mode {
	try {
		const value = localStorage.getItem('lang');
		if (value === 'en' || value === 'ko') return value;
	} catch { /* The selector also works when browser storage is disabled. */ }
	return 'auto';
}

function regionalLanguage(): string {
	for (const tag of [...(navigator.languages || []), navigator.language]) {
		if (!tag) continue;
		try {
			const locale = new Intl.Locale(tag);
			if (!locale.language || locale.language === 'und') continue;
			// Chinese language packs distinguish simplified and traditional scripts.
			if (locale.language === 'zh' && locale.maximize().script === 'Hant') return 'zh-Hant';
			return locale.script ? `${locale.language}-${locale.script}` : locale.language;
		} catch { /* Try the next preferred language. */ }
	}
	const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
	return zone === 'Asia/Seoul' || zone === 'Asia/Pyongyang' ? 'ko' : 'en';
}

type Phrase = {
	english: string;
	korean?: string;
	machine: boolean;
	write: (value: string) => void;
};

function pagePhrases(): Phrase[] {
	const phrases: Phrase[] = [];
	const excluded = 'script,style,noscript,svg,pre,code,#language-menu,[data-language-version="ko"]';
	const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
	while (walker.nextNode()) {
		const node = walker.currentNode as Text;
		const parent = node.parentElement;
		const english = node.data.trim();
		if (!english || !parent || parent.closest(excluded)) continue;
		const korean = parent.dataset.ko;
		const machine = !parent.closest('[translate="no"]') && /\p{L}/u.test(english);
		if (!machine && !korean) continue;
		const original = node.data;
		phrases.push({
			english, korean, machine,
			write: value => { node.data = original.replace(english, () => value); },
		});
	}
	for (const attr of ['alt', 'aria-label', 'title', 'content']) {
		for (const element of document.querySelectorAll(`[data-ko-${attr}]`)) {
			phrases.push({
				english: element.getAttribute(attr) || '',
				korean: element.getAttribute(`data-ko-${attr}`) || undefined,
				machine: !element.closest('[translate="no"]'),
				write: value => element.setAttribute(attr, value),
			});
		}
	}
	return phrases;
}

export function initLanguageMenu() {
	const menu = document.querySelector<HTMLDetailsElement>('#language-menu')!;
	const trigger = menu.querySelector('summary')!;
	const choices = menu.querySelectorAll<HTMLButtonElement>('button[data-mode]');
	const selected = menu.querySelector<HTMLElement>('#selected-language')!;
	const suggested = menu.querySelector<HTMLElement>('#auto-language')!;
	const status = menu.querySelector<HTMLElement>('#translation-status')!;
	const phrases = pagePhrases();
	let mode = savedMode();
	let pending: AbortController | undefined;

	function renderLanguage(lang: string, translations?: Map<string, string>) {
		for (const phrase of phrases) {
			const text = lang === 'ko' ? phrase.korean : phrase.machine && translations?.get(phrase.english);
			phrase.write(text || phrase.english);
		}
		document.documentElement.lang = lang;
		document.documentElement.dir = /^(ar|he|fa|ur)(-|$)/.test(lang) ? 'rtl' : 'ltr';
		const label = lang === 'ko' ? '언어 선택' : (translations?.get('Select language') || 'Select language');
		trigger.setAttribute('aria-label', `${label} (${selected.textContent})`);
		trigger.title = label;
	}

	async function applyMode(userSelected = false) {
		pending?.abort();
		const job = new AbortController();
		pending = job;
		const regional = regionalLanguage();
		const language = mode === 'auto' ? regional : mode;
		const names = typeof Intl.DisplayNames === 'function' ? new Intl.DisplayNames([regional], { type: 'language' }) : null;
		const name = names?.of(regional) || regional;
		suggested.textContent = name;
		suggested.lang = regional;
		selected.textContent = mode === 'ko' ? 'KR' : mode === 'en' ? 'EN' : 'Auto';
		choices.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
		status.textContent = '';
		if (/^(en|ko)(-|$)/.test(language)) {
			renderLanguage(language.split('-')[0]);
			return;
		}

		renderLanguage('en');
		const api = (window as Window & { Translator?: BrowserTranslator }).Translator;
		const fallback = `Translation to ${name} is unavailable. Showing English.`;
		if (!api) {
			status.textContent = fallback;
			return;
		}

		const pair = { sourceLanguage: 'en', targetLanguage: language };
		const { signal } = job;
		let session: TranslatorSession | undefined;
		try {
			const availability = await api.availability(pair);
			if (signal.aborted) return;
			if (availability === 'unavailable') {
				status.textContent = fallback;
				return;
			}
			if (availability !== 'available' && !userSelected) {
				status.textContent = `Select Auto to download the ${name} language pack.`;
				return;
			}
			status.textContent = `Preparing the ${name} language pack…`;
			session = await api.create({ ...pair, signal });
			if (signal.aborted) return;
			status.textContent = `Translating to ${name}…`;
			const words = new Set(phrases.filter(phrase => phrase.machine).map(phrase => phrase.english));
			words.add('Select language');
			const translated = new Map<string, string>();
			for (const text of words) {
				if (signal.aborted) return;
				translated.set(text, await session.translate(text, { signal }));
			}
			if (signal.aborted) return;
			renderLanguage(language, translated);
			status.textContent = '';
		} catch (error) {
			if (!signal.aborted) {
				const needsClick = !userSelected && error instanceof DOMException && error.name === 'NotAllowedError';
				status.textContent = needsClick ? `Select Auto to translate to ${name}.` : fallback;
			}
		} finally {
			session?.destroy();
		}
	}

	for (const button of choices) {
		button.addEventListener('click', () => {
			mode = button.dataset.mode as Mode;
			try { localStorage.setItem('lang', mode); } catch { /* In-memory choice still applies. */ }
			void applyMode(true);
			// Keep download progress or an English fallback explanation visible.
			if (mode !== 'auto' || /^(en|ko)(-|$)/.test(regionalLanguage())) {
				menu.open = false;
				trigger.focus();
			}
		});
	}
	document.addEventListener('click', event => {
		if (!menu.contains(event.target as Node)) menu.open = false;
	});
	menu.addEventListener('keydown', event => {
		if (event.key === 'Escape') {
			menu.open = false;
			trigger.focus();
		}
	});
	window.addEventListener('languagechange', () => { void applyMode(); });
	window.addEventListener('pageshow', event => {
		if (event.persisted) {
			mode = savedMode();
			void applyMode();
		}
	});
	void applyMode();
}
