(function expose(global) {
  const STRINGS = {
    zh: {
      sources: '来源',
      nav: '故事章节',
      hint: '滚动推进故事',
      empty: '这个项目还没有章节，请先在 content/story.json 中补充。',
      chapter: '章节',
    },
    en: {
      sources: 'Sources',
      nav: 'Story chapters',
      hint: 'Move through the story',
      empty: 'This project has no chapters yet. Add them to content/story.json.',
      chapter: 'Chapter',
    },
  };

  // Review aid: a machine with OS animations disabled reports reduce, which hides
  // the designed motion entirely. ?motion=full|reduce overrides it for review only;
  // with no parameter the operating system's preference always wins.
  function resolveReducedMotion() {
    const forced = new URLSearchParams(global.location.search).get('motion');
    if (forced === 'full') return false;
    if (forced === 'reduce') return true;
    return matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  global.mountMotionHTML = function mountMotionHTML(container, config) {
    const chapters = Array.isArray(config.chapters) ? config.chapters : [];
    const connectorUrls = Array.isArray(config.connectors) ? config.connectors : [];
    const strings = STRINGS[config.lang] || STRINGS.en;
    const reduced = resolveReducedMotion();
    // The stylesheet must follow this one decision rather than re-asking the OS:
    // a plain media query would override the ?motion=full review override with
    // !important and make the drift impossible to inspect on a machine whose
    // operating system has animations switched off.
    document.documentElement.dataset.motion = reduced ? 'reduce' : 'full';
    // Image mode never requests a clip: no fetch, no <video>, no seek loop.
    const videoEnabled = config.mediaMode === 'video' && !reduced;
    // A video seam is frame-matched, so a short fade only has to hide the join.
    // Image seams join two unrelated frames, so the dissolve carries the whole
    // transition and has to be long enough to read as one.
    const dissolveVh = typeof config.crossfade === 'number' && config.crossfade > 0
      ? config.crossfade
      : (videoEnabled ? 0.14 : 0.8);
    const handoffVh = 0.14;
    // With no clip footage the still's own drift carries the motion, so the range is
    // scaled for reading across a chapter instead of as a placeholder for a loading clip.
    const driftRange = typeof config.drift === 'number' && config.drift >= 0
      ? config.drift
      : (videoEnabled ? 0.06 : 0.16);

    const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
    const smooth = (value) => {
      const x = clamp(value);
      return x * x * (3 - 2 * x);
    };
    const node = (tag, className) => {
      const element = document.createElement(tag);
      element.className = className || '';
      return element;
    };
    const escapeHtml = (value) => String(value).replace(
      /[&<>"]/g,
      (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[character]),
    );
    const pad = (value) => String(value).padStart(2, '0');

    let destroyed = false;
    const controllers = new Set();

    container.className = 'mh-root';
    container.replaceChildren();
    document.documentElement.dataset.ui = config.ui || 'folio';

    const stage = node('div', 'mh-stage');
    const copyLayer = node('div', 'mh-copy-layer');
    const header = node('header', 'mh-header');
    const brand = node('a', 'mh-brand');
    brand.href = '#top';
    brand.innerHTML = `
      ${config.kicker ? `<span>${escapeHtml(config.kicker)}</span>` : ''}
      <strong>${escapeHtml(config.title || '')}</strong>
      ${config.subtitle ? `<i>${escapeHtml(config.subtitle)}</i>` : ''}`;
    const chapterStatus = node('p', 'mh-header__status');
    const sourceLink = node('a', 'mh-header__source');
    sourceLink.href = '#sources';
    sourceLink.textContent = strings.sources;
    header.append(brand, chapterStatus, sourceLink);

    const progress = node('div', 'mh-progress');
    const progressFill = node('i');
    progress.appendChild(progressFill);
    const navigation = node('nav', 'mh-route');
    navigation.setAttribute('aria-label', strings.nav);
    const hint = node('div', 'mh-hint');
    hint.innerHTML = `<span>${escapeHtml(strings.hint)}</span><i aria-hidden="true"></i>`;
    const track = node('div', 'mh-track');
    container.append(stage, copyLayer, header, progress, navigation, hint, track);

    if (!chapters.length) {
      const empty = node('div', 'mh-empty');
      empty.setAttribute('role', 'status');
      empty.textContent = strings.empty;
      stage.appendChild(empty);
      return function destroy() {};
    }

    const segments = [];
    const sceneSegments = [];
    chapters.forEach((chapter, chapterIndex) => {
      const scene = {
        kind: 'scene',
        chapterIndex,
        still: chapter.still,
        clip: chapter.clip,
        units: chapter.span || 4.6,
        linger: chapter.linger || 0,
      };
      segments.push(scene);
      sceneSegments.push(scene);
      if (chapterIndex < chapters.length - 1 && connectorUrls[chapterIndex]) {
        segments.push({
          kind: 'connector',
          chapterIndex,
          still: chapter.still,
          clip: connectorUrls[chapterIndex],
          units: config.connectorSpan || 1.2,
          linger: 0,
        });
      }
    });

    segments.forEach((segment, index) => {
      const shot = node('div', 'mh-shot');
      shot.dataset.kind = segment.kind;
      const chapter = chapters[segment.chapterIndex] || {};
      const fallback = node('div', 'mh-shot__fallback');
      fallback.innerHTML = `<span>${pad(index + 1)}</span><strong>${escapeHtml(chapter.label || chapter.title || '')}</strong>`;
      const poster = node('img', 'mh-shot__poster');
      poster.alt = segment.kind === 'scene' ? (chapter.label || chapter.title || '') : '';
      poster.decoding = 'async';
      poster.loading = index < 2 ? 'eager' : 'lazy';
      if (segment.still) poster.src = segment.still;
      poster.addEventListener('error', () => shot.classList.add('is-missing'));
      shot.append(fallback, poster);
      stage.appendChild(shot);
      Object.assign(segment, {
        shot,
        poster,
        video: null,
        loading: false,
        failed: false,
        ready: false,
        visible: false,
        current: 0,
        target: 0,
      });
    });

    const copies = [];
    const navButtons = [];
    chapters.forEach((chapter, index) => {
      const article = node('article', 'mh-copy');
      article.dataset.position = chapter.copyPosition || (index % 2 ? 'right' : 'left');
      if (chapter.accent) article.style.setProperty('--mh-scene-accent', chapter.accent);
      const paragraphs = (chapter.paragraphs || []).map((text) => `<p>${escapeHtml(text)}</p>`).join('');
      const tags = (chapter.tags || []).map((text) => `<li>${escapeHtml(text)}</li>`).join('');
      article.innerHTML = `
        <p class="mh-copy__index">${pad(index + 1)} <span>/</span> ${pad(chapters.length)}</p>
        ${chapter.eyebrow ? `<p class="mh-copy__eyebrow">${escapeHtml(chapter.eyebrow)}</p>` : ''}
        <h2>${escapeHtml(chapter.title || '')}</h2>
        ${chapter.subtitle ? `<p class="mh-copy__subtitle">${escapeHtml(chapter.subtitle)}</p>` : ''}
        <div class="mh-copy__body">${paragraphs}</div>
        ${tags ? `<ul class="mh-copy__tags">${tags}</ul>` : ''}`;
      article.inert = true;
      article.setAttribute('aria-hidden', 'true');
      copyLayer.appendChild(article);
      copies.push(article);

      const button = node('button', 'mh-route__item');
      button.type = 'button';
      button.innerHTML = `<span>${pad(index + 1)}</span><i>${escapeHtml(chapter.label || chapter.title || '')}</i>`;
      button.setAttribute('aria-label', `Go to ${chapter.label || chapter.title || `${strings.chapter} ${index + 1}`}`);
      button.addEventListener('click', () => {
        // Not the raw segment start: a chapter's copy fades in over the first part
        // of its own range, so landing on the boundary would show the image with no
        // words at all. Land where the copy has settled instead.
        const target = sceneSegments[index]?.copySettled ?? 0;
        scrollTo({ top: target, behavior: reduced ? 'auto' : 'smooth' });
      });
      navigation.appendChild(button);
      navButtons.push(button);
    });

    let viewportHeight = innerHeight;
    let viewportWidth = innerWidth;
    let totalUnits = 0;
    let readQueued = false;
    let activeChapter = -1;
    let rafId = 0;

    function layout() {
      viewportHeight = innerHeight;
      viewportWidth = innerWidth;
      let offset = 0;
      segments.forEach((segment) => {
        segment.start = offset * viewportHeight;
        offset += segment.units;
        segment.end = offset * viewportHeight;
      });
      totalUnits = offset;
      // The copy of a chapter fades in over the first part of its own range, so the
      // distance where it has settled is also where a chapter jump should land.
      // One formula serves both, so navigation cannot drift from the copy timing.
      sceneSegments.forEach((scene, index) => {
        const span = Math.max(1, scene.end - scene.start);
        const fadePx = Math.max(span * 0.09, Math.max(1, viewportHeight * dissolveVh) * 0.5);
        scene.fadePx = fadePx;
        scene.copySettled = index === 0
          ? scene.start
          : Math.min(scene.start + fadePx, Math.max(scene.start, scene.end - 1));
      });
      track.style.height = `${(totalUnits + 1) * viewportHeight}px`;
      read();
    }

    function loadClip(segment) {
      if (!videoEnabled || destroyed || segment.loading || segment.failed || segment.ready || !segment.clip) {
        return;
      }
      segment.loading = true;
      const controller = new AbortController();
      controllers.add(controller);
      fetch(segment.clip, { signal: controller.signal })
        .then((response) => (response.ok ? response.blob() : Promise.reject(new Error(String(response.status)))))
        .then((blob) => {
          if (destroyed) return;
          const video = node('video', 'mh-shot__video');
          video.muted = true;
          video.playsInline = true;
          video.preload = 'auto';
          video.src = URL.createObjectURL(blob);
          video.addEventListener('loadedmetadata', () => {
            if (destroyed) return;
            segment.ready = true;
            // Nudge off zero so a decoded frame paints and the poster can hand over.
            if (video.currentTime === 0) {
              try {
                video.currentTime = 0.001;
              } catch (error) {
                /* keep the poster */
              }
            }
            scheduleRead();
          });
          video.addEventListener('seeked', () => {
            if (!destroyed) segment.shot.classList.add('has-video');
          }, { once: true });
          video.addEventListener('error', () => {
            if (destroyed) return;
            segment.failed = true;
            segment.shot.classList.add('is-missing');
          });
          segment.shot.appendChild(video);
          segment.video = video;
        })
        .catch((error) => {
          if (destroyed || error?.name === 'AbortError') return;
          segment.failed = true;
          segment.loading = false;
          segment.shot.classList.add('is-missing');
        });
    }

    function unloadClip(segment) {
      if (!segment.video) return;
      const source = segment.video.src;
      segment.video.remove();
      if (source.startsWith('blob:')) URL.revokeObjectURL(source);
      segment.video = null;
      segment.loading = false;
      segment.ready = false;
      segment.failed = false;
      segment.current = 0;
      segment.target = 0;
      segment.shot.classList.remove('has-video');
    }

    function distanceTo(y, segment) {
      if (y < segment.start) return segment.start - y;
      if (y > segment.end) return y - segment.end;
      return 0;
    }

    function remapWithLinger(progress, amount) {
      if (!amount) return progress;
      const hold = clamp(amount, 0, 0.6) * 0.38;
      const left = 0.5 - hold;
      const right = 0.5 + hold;
      if (progress < left) return progress * (0.5 / left);
      if (progress > right) return 0.5 + (progress - right) * (0.5 / (1 - right));
      return 0.5;
    }

    function read() {
      const y = scrollY;
      const dissolve = Math.max(1, viewportHeight * dissolveVh);
      const handoff = Math.max(1, viewportHeight * handoffVh);
      const loadDistance = viewportHeight * 2.2;
      const releaseDistance = viewportHeight * 4.5;
      let currentSegment = segments[0];

      segments.forEach((segment, index) => {
        const local = clamp((y - segment.start) / Math.max(1, segment.end - segment.start));
        // The arriving scene dissolves in on top of the departing one, which stays
        // fully opaque underneath. Ramping both down at once would let the dark
        // stage bleed through and dip the whole frame toward black mid-transition.
        let opacity = 1;
        if (y < segment.start && index > 0) {
          opacity = smooth(1 - (segment.start - y) / dissolve);
        } else if (y > segment.end && index < segments.length - 1) {
          opacity = smooth(1 - (y - segment.end) / handoff);
        }
        segment.shot.style.opacity = opacity;
        segment.visible = opacity > 0.01;
        segment.target = remapWithLinger(local, segment.linger);
        if (y >= segment.start) currentSegment = segment;
        if (videoEnabled) {
          if (distanceTo(y, segment) < loadDistance) loadClip(segment);
          else if (distanceTo(y, segment) > releaseDistance) unloadClip(segment);
        }
        if (!reduced && !segment.ready) {
          // The still has to carry the motion itself in image mode, so the drift is
          // sized to be read across a whole chapter rather than as a load placeholder.
          const drift = segment.kind === 'scene' && segment.chapterIndex % 2 === 1
            ? 1.02 + (1 - local) * driftRange
            : 1.02 + local * driftRange;
          segment.poster.style.transform = `scale(${drift.toFixed(4)})`;
        }
      });

      chapters.forEach((chapter, index) => {
        const scene = sceneSegments[index];
        const inside = y >= scene.start && y <= scene.end;
        // Clear the copy before the image settles so the words never fight the
        // dissolve, and bring the next scene's copy in only after its own segment
        // starts. The window is shared with the chapter-jump target in layout().
        const fadePx = scene.fadePx;
        const enter = index === 0 ? 1 : smooth((y - scene.start) / fadePx);
        const leave = index === chapters.length - 1 ? 1 : smooth((scene.end - y) / fadePx);
        const opacity = inside ? Math.min(enter, leave) : (index === chapters.length - 1 && y > scene.end ? 1 : 0);
        const active = opacity > 0.5;
        copies[index].style.opacity = opacity;
        copies[index].style.pointerEvents = opacity > 0.7 ? 'auto' : 'none';
        if (copies[index].inert === active) {
          copies[index].inert = !active;
          if (active) copies[index].removeAttribute('aria-hidden');
          else copies[index].setAttribute('aria-hidden', 'true');
        }
      });

      const localChapter = currentSegment.kind === 'scene'
        ? currentSegment.chapterIndex
        : currentSegment.chapterIndex + (currentSegment.target >= 0.5 ? 1 : 0);
      if (localChapter !== activeChapter) {
        activeChapter = localChapter;
        const chapter = chapters[activeChapter] || {};
        chapterStatus.textContent = `${pad(activeChapter + 1)} — ${chapter.label || chapter.title || ''}`;
        navButtons.forEach((button, index) => {
          button.classList.toggle('is-active', index === activeChapter);
          if (index === activeChapter) button.setAttribute('aria-current', 'step');
          else button.removeAttribute('aria-current');
        });
      }

      const maximum = Math.max(1, totalUnits * viewportHeight);
      progressFill.style.transform = `scaleX(${clamp(y / maximum)})`;
      hint.classList.toggle('is-hidden', y > viewportHeight * 0.2);
      readQueued = false;
    }

    function scheduleRead() {
      if (destroyed || readQueued) return;
      readQueued = true;
      requestAnimationFrame(read);
    }

    function animate() {
      rafId = 0;
      if (destroyed || !videoEnabled) return;
      segments.forEach((segment) => {
        if (!segment.visible || !segment.ready || !segment.video || segment.video.seeking) return;
        segment.current += (segment.target - segment.current) * 0.2;
        const targetTime = clamp(segment.current, 0, 0.999) * (segment.video.duration || 1);
        if (Math.abs(segment.video.currentTime - targetTime) > 0.01) segment.video.currentTime = targetTime;
      });
      startLoop();
    }

    function startLoop() {
      if (destroyed || !videoEnabled || rafId || document.hidden) return;
      rafId = requestAnimationFrame(animate);
    }

    function stopLoop() {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
    }

    function primeVideos() {
      if (!videoEnabled) return;
      segments.forEach((segment) => {
        if (!segment.video) return;
        const promise = segment.video.play();
        if (promise?.then) promise.then(() => segment.video.pause()).catch(() => {});
      });
    }

    function onResize() {
      if (innerWidth === viewportWidth && Math.abs(innerHeight - viewportHeight) < 80) return;
      layout();
    }

    function onVisibility() {
      if (document.hidden) stopLoop();
      else startLoop();
    }

    addEventListener('scroll', scheduleRead, { passive: true });
    addEventListener('resize', onResize);
    addEventListener('touchstart', primeVideos, { once: true, passive: true });
    addEventListener('pointerdown', primeVideos, { once: true, passive: true });
    document.addEventListener('visibilitychange', onVisibility);
    layout();
    startLoop();

    return function destroy() {
      if (destroyed) return;
      destroyed = true;
      stopLoop();
      removeEventListener('scroll', scheduleRead);
      removeEventListener('resize', onResize);
      removeEventListener('touchstart', primeVideos);
      removeEventListener('pointerdown', primeVideos);
      document.removeEventListener('visibilitychange', onVisibility);
      controllers.forEach((controller) => controller.abort());
      controllers.clear();
      segments.forEach((segment) => {
        const source = segment.video?.src;
        if (source?.startsWith('blob:')) URL.revokeObjectURL(source);
      });
    };
  };
})(window);
