(async function boot() {
  const STRINGS = {
    zh: {
      loading: '正在载入故事…',
      unreachable: '无法读取故事数据。请通过 HTTP 打开本项目，不要直接双击 index.html。',
      invalid: '故事数据不完整，页面无法渲染：',
      sources: '来源',
      sourcesTitle: '研究与改编',
      close: '关闭',
      noSources: '未提供来源。',
    },
    en: {
      loading: 'Preparing the story…',
      unreachable: 'Could not load the story data. Open this project through HTTP rather than double-clicking index.html.',
      invalid: 'The story data is incomplete, so the page cannot render: ',
      sources: 'Sources',
      sourcesTitle: 'Research and adaptation',
      close: 'Close',
      noSources: 'No sources were provided.',
    },
  };
  const MEDIA_MODES = ['images', 'video'];
  const SAFE_PROTOCOLS = ['http:', 'https:'];
  const CJK = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;

  // Projects this skill initializes always declare meta.lang. A story authored
  // elsewhere may not, and defaulting to English would give Chinese content an
  // English interface, so fall back to the content's own script.
  function detectLang(meta, chapters) {
    const parts = [meta.title, meta.subtitle, meta.kicker, meta.description];
    for (const chapter of chapters) {
      if (!chapter || typeof chapter !== 'object') continue;
      parts.push(chapter.title, chapter.label, chapter.eyebrow, chapter.subtitle);
      if (Array.isArray(chapter.paragraphs)) parts.push(...chapter.paragraphs);
    }
    return CJK.test(parts.filter(Boolean).join(' ')) ? 'zh' : 'en';
  }

  const root = document.getElementById('experience');
  const bootScreen = document.getElementById('boot');
  const dialog = document.getElementById('sources');
  const bootLabel = bootScreen ? bootScreen.querySelector('span') : null;

  let strings = STRINGS.en;

  function fail(message) {
    if (bootScreen) {
      bootScreen.textContent = message;
      bootScreen.classList.remove('is-hidden');
    } else if (root) {
      root.textContent = message;
    }
  }

  try {
    const response = await fetch('content/story.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`content/story.json returned HTTP ${response.status}`);

    let story;
    try {
      story = await response.json();
    } catch (error) {
      throw new Error(`content/story.json is not valid JSON (${error.message})`);
    }

    const problems = [];
    if (!story || typeof story !== 'object' || Array.isArray(story)) {
      problems.push('the root value must be an object');
    } else {
      if (!story.meta || typeof story.meta !== 'object') problems.push('"meta" is missing');
      if (!Array.isArray(story.chapters)) problems.push('"chapters" must be a list');
      else if (!story.chapters.length) problems.push('"chapters" must contain at least one chapter');
    }
    if (problems.length) throw new Error(problems.join('; '));

    const meta = story.meta;
    const lang = meta.lang === 'zh' || meta.lang === 'en'
      ? meta.lang
      : detectLang(meta, Array.isArray(story.chapters) ? story.chapters : []);
    if (meta.lang === undefined) {
      console.info(`meta.lang is missing; rendering the interface as "${lang}" based on the content.`);
    }
    strings = STRINGS[lang] || STRINGS.en;
    if (bootLabel) bootLabel.textContent = strings.loading;

    const declaredMode = meta.mediaMode;
    // Match the CLI's inference: a story that declares clips or connectors is a
    // video project even when the field is missing, so the page and the checker
    // never disagree about what a project is.
    const declaresVideo = story.chapters.some((chapter) => chapter && chapter.clip) ||
      (Array.isArray(story.connectors) && story.connectors.some(Boolean));
    const inferredMode = declaresVideo ? 'video' : 'images';
    const mediaMode = MEDIA_MODES.includes(declaredMode) ? declaredMode : inferredMode;
    if (declaredMode === undefined && inferredMode === 'video') {
      console.info('meta.mediaMode is missing; treating this project as video because it declares clips.');
    }
    if (declaredMode !== undefined && !MEDIA_MODES.includes(declaredMode)) {
      console.warn(`Unknown meta.mediaMode ${JSON.stringify(declaredMode)}; falling back to ${inferredMode}.`);
    }

    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    if (meta.title) document.title = meta.title;
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = meta.description || meta.subtitle || meta.title || '';
    document.documentElement.dataset.style = meta.style || 'cinematic';
    document.documentElement.dataset.ui = meta.ui || 'folio';
    if (meta.accent) document.documentElement.style.setProperty('--mh-accent', meta.accent);

    window.mountMotionHTML(root, {
      title: meta.title,
      kicker: meta.kicker,
      subtitle: meta.subtitle,
      ui: meta.ui || 'folio',
      lang,
      mediaMode,
      crossfade: typeof meta.crossfade === 'number' ? meta.crossfade : undefined,
      drift: typeof meta.drift === 'number' ? meta.drift : undefined,
      chapters: story.chapters,
      connectors: Array.isArray(story.connectors) ? story.connectors : [],
      connectorSpan: meta.connectorSpan || 1.2,
    });

    const eyebrow = document.getElementById('sources-eyebrow');
    const heading = document.getElementById('sources-title');
    const closeButton = dialog ? dialog.querySelector('[data-close]') : null;
    if (eyebrow) eyebrow.textContent = strings.sources;
    if (heading) heading.textContent = strings.sourcesTitle;
    if (closeButton) closeButton.setAttribute('aria-label', strings.close);

    const note = document.getElementById('adaptation-note');
    if (note) note.textContent = meta.note || '';

    const sourceList = document.getElementById('source-list');
    if (sourceList) {
      sourceList.replaceChildren();
      for (const source of Array.isArray(story.sources) ? story.sources : []) {
        if (!source || typeof source !== 'object') continue;
        const label = String(source.label || source.url || '');
        let href = null;
        try {
          const parsed = new URL(String(source.url || ''), location.href);
          if (SAFE_PROTOCOLS.includes(parsed.protocol)) href = parsed.href;
        } catch (error) {
          href = null;
        }
        const item = document.createElement('li');
        if (href) {
          const link = document.createElement('a');
          link.href = href;
          link.textContent = label;
          link.target = '_blank';
          link.rel = 'noreferrer';
          item.appendChild(link);
        } else {
          // Never turn story data into a navigable javascript:/data: link.
          item.textContent = label;
        }
        sourceList.appendChild(item);
      }
      if (!sourceList.childElementCount) {
        const item = document.createElement('li');
        item.textContent = strings.noSources;
        sourceList.appendChild(item);
      }
    }

    if (dialog) {
      document.addEventListener('click', (event) => {
        if (event.target.closest('a[href="#sources"]')) {
          event.preventDefault();
          dialog.showModal();
        }
      });
      const close = dialog.querySelector('[data-close]');
      if (close) close.addEventListener('click', () => dialog.close());
      dialog.addEventListener('click', (event) => {
        if (event.target === dialog) dialog.close();
      });
    }
  } catch (error) {
    console.error(error);
    fail(`${strings.unreachable}\n${error.message}`);
    return;
  }

  if (bootScreen) {
    bootScreen.classList.add('is-hidden');
    setTimeout(() => bootScreen.remove(), 400);
  }
})();
