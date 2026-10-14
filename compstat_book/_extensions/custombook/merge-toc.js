document.addEventListener("DOMContentLoaded", function() {

  // --- CONFIG ---
  const REMOVE_UNNUMBERED_FROM_TOC = true; 

  // --- HELPER: FORMAT NUMBERS ---
  function formatLinkText(link) {
    let container = link.querySelector('.menu-text') || link;
    if (container.querySelector('.toc-num')) return false;

    const text = container.innerText;
    if (!text) return false;

    const match = text.match(/^([\d\w\.]+\.?)(\s+)(.*)/);

    if (match) {
      container.innerHTML = `<span class="toc-num">${match[1]}</span><span class="toc-text">${match[3]}</span>`;
      link.classList.add('is-numbered');
      return true;
    } else {
      if (REMOVE_UNNUMBERED_FROM_TOC && link.closest('.injected-page-toc')) {
          const li = link.closest('li');
          if (li) li.remove();
          return false; 
      }
      link.classList.add('is-unnumbered');
      return true;
    }
  }

  // --- PART A: FORMAT CHAPTERS ---
  function formatChapters() {
    const items = document.querySelectorAll('#quarto-sidebar .sidebar-item');
    items.forEach(li => {
      const link = li.querySelector('.sidebar-link');
      const toggleBtn = li.querySelector('.sidebar-item-toggle');

      if (link) {
        formatLinkText(link);
        
        if (toggleBtn) {
          link.classList.add('has-children');
          if (li.classList.contains('sidebar-item-collapsed')) {
             link.classList.add('collapsed');
          } else {
             link.classList.add('expanded');
          }

          if (!link.dataset.hasListener) {
            link.addEventListener('click', (e) => {
               e.stopPropagation(); 
               if (link.classList.contains('collapsed')) {
                   link.classList.remove('collapsed');
                   link.classList.add('expanded');
               } else {
                   link.classList.add('collapsed');
                   link.classList.remove('expanded');
               }
               toggleBtn.click();
            });
            link.dataset.hasListener = "true";
          }
        }
      }
    });
  }

  // --- PART B: INJECT PAGE TOC ---
  function moveToc() {
    const toc = document.querySelector('nav[role="doc-toc"]');
    const activeLink = document.querySelector('.sidebar-link.active');

    if (toc && activeLink) {
      const parentLi = activeLink.closest('.sidebar-item');
      if (parentLi && !parentLi.querySelector('.injected-page-toc')) {
        const tocList = toc.querySelector('ul');
        if (tocList) {
            const clonedList = tocList.cloneNode(true);
            clonedList.className = 'injected-page-toc';

            const links = clonedList.querySelectorAll('a');
            links.forEach(link => formatLinkText(link));

            const parents = clonedList.querySelectorAll('li');
            parents.forEach(li => {
                if (li.querySelector('ul')) { 
                    const link = li.querySelector('a');
                    const subList = li.querySelector('ul');
                    if (link && subList) {
                        link.classList.add('has-children');
                        link.classList.add('collapsed'); 
                        subList.style.display = 'none';

                        if (!link.dataset.hasListener) {
                            link.addEventListener('click', (e) => {
                                e.stopPropagation();
                                if (subList.style.display === 'none') {
                                    subList.style.display = 'block';
                                    link.classList.remove('collapsed');
                                    link.classList.add('expanded');
                                } else {
                                    subList.style.display = 'none';
                                    link.classList.remove('expanded');
                                    link.classList.add('collapsed');
                                }
                            });
                            link.dataset.hasListener = "true";
                        }
                    }
                }
            });
            parentLi.appendChild(clonedList);
            syncActiveState(clonedList); 
        }
      }
    }
  }

  // --- PART C: LIVE SYNC (Title Priority Fix) ---
  function syncActiveState(injectedToc) {
    const tocLinks = injectedToc.querySelectorAll('a');
    tocLinks.forEach(l => l.classList.remove('active')); 
    tocLinks.forEach(l => l.classList.remove('toc-active')); 

    const headers = document.querySelectorAll('main h1, main h2, main h3, main h4, main h5, main h6');
    const idToLink = {};
    
    tocLinks.forEach(link => {
        const href = link.getAttribute('href');
        if(href && href.startsWith('#')) {
            const id = href.substring(1);
            idToLink[id] = link;
            idToLink[decodeURIComponent(id)] = link; 
        }
    });

    const titleObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                tocLinks.forEach(l => l.classList.remove('toc-active'));
            }
        });
    }, { rootMargin: '0px 0px -50% 0px' }); 

    const mainTitle = document.querySelector('main h1');
    if (mainTitle) titleObserver.observe(mainTitle);

    const contentObserverOptions = {
        root: null,
        rootMargin: '0px 0px -80% 0px', 
        threshold: 0
    };

    const contentObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                if (window.scrollY < 100) return; 

                const id = entry.target.getAttribute('id');
                const activeSubLink = idToLink[id];
                
                if (activeSubLink) {
                    tocLinks.forEach(l => l.classList.remove('toc-active'));
                    activeSubLink.classList.add('toc-active');
                    
                    const parentUl = activeSubLink.closest('ul');
                    if (parentUl && parentUl.style.display === 'none') {
                           parentUl.style.display = 'block';
                           const pLink = parentUl.parentElement.querySelector('a.has-children');
                           if (pLink) {
                               pLink.classList.remove('collapsed');
                               pLink.classList.add('expanded');
                           }
                    }
                }
            }
        });
    }, contentObserverOptions);

    headers.forEach(header => {
        if (header.tagName !== 'H1') {
            contentObserver.observe(header);
        }
    });
  }

  // --- PART D: SIDEBAR TOGGLE ---
  function createSidebarToggle() {
    if (document.getElementById('custom-sidebar-toggle')) return;
    const btn = document.createElement("button");
    btn.id = "custom-sidebar-toggle";
    btn.innerHTML = '&#9776;'; 
    btn.title = "Toggle Sidebar";
    document.body.insertAdjacentElement('afterbegin', btn);
    btn.addEventListener("click", function() {
      document.body.classList.toggle("sidebar-closed");
    });
  }


  // --- PART E: DRAGGABLE SIDEBAR WIDTH ---
  // Drag the thin handle on the right edge of the sidebar to change its width;
  // double-click it to restore the default. The width is remembered in localStorage.
  function createSidebarResizer() {
    if (document.getElementById('sidebar-resizer')) return;
    const MIN = 180, MAX = 700, KEY = 'sidebar-width';
    const root = document.documentElement;
    const clamp = w => Math.max(MIN, Math.min(Math.min(MAX, window.innerWidth - 300), w));
    const defaultWidth = getComputedStyle(root).getPropertyValue('--quarto-sidebar-width').trim();
    const setWidth = w => root.style.setProperty('--quarto-sidebar-width', clamp(w) + 'px');

    try {
      const saved = parseInt(localStorage.getItem(KEY));
      if (saved) setWidth(saved);
    } catch (e) { /* storage may be blocked */ }

    const handle = document.createElement('div');
    handle.id = 'sidebar-resizer';
    handle.title = 'Drag to resize the sidebar (double-click to reset)';
    document.body.appendChild(handle);

    handle.addEventListener('pointerdown', function(e) {
      e.preventDefault();
      handle.setPointerCapture(e.pointerId);
      document.body.classList.add('sidebar-resizing');
    });
    handle.addEventListener('pointermove', function(e) {
      if (!document.body.classList.contains('sidebar-resizing')) return;
      setWidth(e.clientX);
    });
    function stop(e) {
      if (!document.body.classList.contains('sidebar-resizing')) return;
      document.body.classList.remove('sidebar-resizing');
      try {
        localStorage.setItem(KEY, String(parseInt(getComputedStyle(root).getPropertyValue('--quarto-sidebar-width'))));
      } catch (err) { /* ignore */ }
    }
    handle.addEventListener('pointerup', stop);
    handle.addEventListener('pointercancel', stop);
    handle.addEventListener('dblclick', function() {
      root.style.setProperty('--quarto-sidebar-width', defaultWidth || '300px');
      try { localStorage.removeItem(KEY); } catch (err) { /* ignore */ }
    });
  }


  // --- PART F: READING SETTINGS (font size, font family, background) ---
  function createReadingSettings() {
    if (document.getElementById('reading-settings')) return;
    const main = document.querySelector('main.content');
    if (!main) return;
    const root = document.documentElement;
    const KEY = 'reading-settings';
    const FONTS = {
      'default': ['Default', ''],
      'sans':    ['Sans-serif', 'Helvetica, Arial, sans-serif'],
      'serif':   ['Serif', 'Georgia, "Times New Roman", Times, serif'],
      'book':    ['Book (Palatino)', '"Palatino Linotype", Palatino, "Book Antiqua", serif'],
      'mono':    ['Monospace', '"SFMono-Regular", Menlo, Consolas, monospace']
    };
    const BACKGROUNDS = [
      ['White',  '#ffffff', '#000000'],
      ['Cream',  '#fbf3e0', '#2b2118'],
      ['Gray',   '#e9ecef', '#1a1a1a'],
      ['Green',  '#e3f1e3', '#16241a'],
      ['Blue',   '#e6eef8', '#14202e']
    ];
    let state = { scale: 1, font: 'default', bg: 0 };
    try { Object.assign(state, JSON.parse(localStorage.getItem(KEY)) || {}); } catch (e) { /* ignore */ }

    function apply() {
      state.scale = Math.max(0.7, Math.min(1.8, Math.round(state.scale * 10) / 10));
      root.style.setProperty('--reading-scale', state.scale);
      const f = FONTS[state.font] || FONTS['default'];
      root.classList.toggle('has-reading-font', !!f[1]);
      root.style.setProperty('--reading-font', f[1] || 'inherit');
      const b = BACKGROUNDS[state.bg] || BACKGROUNDS[0];
      root.style.setProperty('--background', b[1]);
      root.style.setProperty('--textcolor', b[2]);
      value.textContent = Math.round(state.scale * 100) + '%';
      fontSel.value = state.font;
      swatches.forEach((s, i) => s.classList.toggle('selected', i === state.bg));
      try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
    }

    const bar = document.createElement('div');
    bar.id = 'reading-settings';

    function group(title) {
      const g = document.createElement('span');
      g.className = 'rs-group'; g.title = title;
      bar.appendChild(g);
      return g;
    }
    function button(parent, text, title, onclick) {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = text; b.title = title;
      b.addEventListener('click', onclick);
      parent.appendChild(b);
      return b;
    }

    const gSize = group('Font size');
    button(gSize, 'A−', 'Smaller text', () => { state.scale -= 0.1; apply(); });
    const value = button(gSize, '100%', 'Reset the text size', () => { state.scale = 1; apply(); });
    value.classList.add('rs-size-value');
    button(gSize, 'A+', 'Larger text', () => { state.scale += 0.1; apply(); });

    const gFont = group('Font family');
    const fontSel = document.createElement('select');
    Object.keys(FONTS).forEach(k => {
      const o = document.createElement('option');
      o.value = k; o.textContent = FONTS[k][0];
      fontSel.appendChild(o);
    });
    fontSel.addEventListener('change', () => { state.font = fontSel.value; apply(); });
    gFont.appendChild(fontSel);

    const gBg = group('Background colour');
    const swatches = BACKGROUNDS.map((b, i) => {
      const s = button(gBg, '', b[0] + ' background', () => { state.bg = i; apply(); });
      s.className = 'rs-swatch';
      s.style.backgroundColor = b[1];
      return s;
    });
    button(gBg, 'Reset', 'Back to the default size, font and background', () => {
      state = { scale: 1, font: 'default', bg: 0 }; apply();
    });

    main.insertBefore(bar, main.firstChild);
    apply();
  }

  // --- EXECUTION ---
  function run() {
    try { createSidebarToggle(); } catch(e) { console.error(e); }
    try { createSidebarResizer(); } catch(e) { console.error(e); }
    try { createReadingSettings(); } catch(e) { console.error(e); }
    try { formatChapters(); } catch(e) { console.error(e); }
    try { moveToc(); } catch(e) { console.error(e); }
    document.querySelector('#quarto-sidebar .sidebar-menu-container')?.classList.add('loaded');
  }

  run();
  setTimeout(run, 500); 
});
