// Visible DOM only; no author fields, cookies or private API payloads.
(sourceUrl, action = 'read') => {
  const visible = el => !!el && !!el.getClientRects().length &&
    !el.closest('[hidden],[aria-hidden="true"]') && getComputedStyle(el).visibility !== 'hidden';
  const clean = text => String(text || '').replace(/\s+/g, ' ').trim();
  const identify = href => {
    try {
      const url = new URL(href, location.href);
      if (url.protocol !== 'https:' || !/(^|\.)facebook\.com$/i.test(url.hostname)) return null;
      return url.pathname.match(/\/(?:posts|permalink|videos|reel)\/(\d+|pfbid[A-Za-z0-9]+)(?:\/|$)/)?.[1] ||
        url.searchParams.get('story_fbid') || url.searchParams.get('fbid') || url.searchParams.get('v');
    } catch { return null; }
  };
  const expected = identify(sourceUrl);
  const ids = el => new Set([...el.querySelectorAll('a[href]')].map(a => identify(a.href)).filter(Boolean));
  const matches = el => { const found = ids(el); return found.size === 1 && found.has(expected); };
  const current = identify(location.href);
  if (!expected || (current && current !== expected)) return action === 'read' ? [] : {status:'wrong_source'};
  const dialogs = [...document.querySelectorAll('[role="dialog"]')].filter(visible);
  let root = dialogs.find(matches);
  if (!root) root = [...document.querySelectorAll('[role="article"]')].find(el => visible(el) &&
    !el.parentElement?.closest('[role="article"]') && matches(el) && !/[?&](?:comment_id|reply_comment_id)=/.test(
      [...el.querySelectorAll('a[href]')].find(a => identify(a.href))?.href || ''));
  if (!root && dialogs.length === 1 && current === expected && ids(dialogs[0]).size === 0) root = dialogs[0];
  if (!root && !dialogs.length && matches(document.body)) root = document.querySelector('[role="main"]') || document.body;
  if (!root) return action === 'read' ? [] : {status:'missing_scope'};
  const boundary = '[role="article"],[aria-label^="Bình luận của"],[aria-label^="Comment by"],'+
    '[aria-label^="Comment from"],[aria-label^="Reply"],[aria-label^="Phản hồi"]';
  const own = (el, selector) => [...el.querySelectorAll(selector)].filter(node => node.closest(boundary) === el);
  const marked = el => /^(comment|reply|bình luận|phản hồi)(\s|:|$)/i.test(el.getAttribute('aria-label') || '');
  const comments = [...root.querySelectorAll(boundary)].filter(el => visible(el) && (marked(el) ||
    own(el, 'a[href]').some(a => /[?&](?:comment_id|reply_comment_id)=\d+/.test(a.href))));
  if (action === 'inspect') return {status:'ready',comment_containers:comments.length};
  const all = /^(?:Tất cả (?:các )?bình luận|All comments)$/i;
  const filtered = /^(?:Phù hợp nhất|Liên quan nhất|Mới nhất|Most relevant|Newest|Top comments)$/i;
  const label = el => clean(el.innerText || el.getAttribute('aria-label'));
  if (action === 'sort') {
    const controls = [...root.querySelectorAll('button,[role="button"]')].filter(el => visible(el) &&
      !comments.some(c => c.contains(el)) && !el.closest('[role="menu"],[role="listbox"]'));
    const trigger = controls.find(el => filtered.test(label(el)));
    if (!trigger) return {status:controls.some(el => all.test(label(el))) ? 'confirmed' : 'unavailable'};
    window.__cmtSort ??= new WeakMap();
    const state = window.__cmtSort.get(root) || {opened:false,attempts:0};
    window.__cmtSort.set(root,state);
    if (++state.attempts > 20) return {status:'failed'};
    if (state.opened) {
      const option = [...document.querySelectorAll('[role="menuitem"],[role="menuitemradio"],[role="option"],[role="button"],button')]
        .find(el => visible(el) && el !== trigger && (!root.contains(el) || el.closest('[role="menu"],[role="listbox"]')) &&
          (el.closest('[role="menu"],[role="listbox"]') || !el.closest(boundary)) &&
          all.test(clean((el.innerText || el.getAttribute('aria-label') || '').split('\n')[0])));
      if (option) return {status:'selecting',element:option};
      if (trigger.getAttribute('aria-expanded') === 'true') return {status:'waiting'};
    }
    state.opened = true;
    return {status:'opening',element:trigger};
  }
  const expansion = /^(?:xem (?:thêm |các |tất cả )?(?:\d+ )?(?:bình luận|phản hồi|câu trả lời)(?: (?:khác|trước|nữa))?|(?:view|see) (?:(?:more|previous|all)(?: \d+)?|\d+(?: more)?) (?:comments|replies)|\d+ (?:phản hồi|câu trả lời|replies|reply))(?: \(\d+\))?$/i;
  const moreText = /^(?:see more|xem thêm)$/i;
  if (action === 'buttons') return [...root.querySelectorAll('button,[role="button"]')].filter(el =>
    visible(el) && !el.matches('[disabled],[aria-disabled="true"]') &&
    (expansion.test(label(el)) || (comments.some(c => c.contains(el)) && moreText.test(label(el)))));
  if (action === 'scroll') {
    const canScroll = el => visible(el) && el.scrollHeight > el.clientHeight + 20 &&
      ['auto','scroll'].includes(getComputedStyle(el).overflowY) && !el.matches('input,textarea,[contenteditable="true"]');
    const targets = [root,...root.querySelectorAll('*')].filter(canScroll);
    targets.sort((a,b) => b.querySelectorAll(boundary).length-a.querySelectorAll(boundary).length);
    const dialog = root.closest('[role="dialog"]');
    for (let p=root.parentElement; p; p=p.parentElement) {
      if (dialog && !dialog.contains(p) && p !== dialog) break;
      if (canScroll(p)) targets.push(p);
      if (p === dialog) break;
    }
    if (!dialog) targets.push(document.scrollingElement);
    for (const target of new Set(targets.filter(Boolean))) {
      const before = target.scrollTop;
      target.scrollBy(0,Math.max(180,target.clientHeight*.7));
      if (target.scrollTop > before) return {moved:true};
    }
    return {moved:false};
  }
  window.__cmtSeen ??= new WeakMap(); window.__cmtSeq ??= 0;
  return comments.flatMap(el => {
    const links = own(el,'a[href]');
    if (links.some(a => identify(a.href) && identify(a.href) !== expected)) return [];
    const link = links.find(a => /[?&](?:comment_id|reply_comment_id)=\d+/.test(a.href));
    let bodies = own(el,'[data-comment-body],[data-ad-preview="message"],[data-ad-comet-preview="message"]').filter(visible);
    if (!bodies.length) bodies = own(el,'[dir="auto"]').filter(node => visible(node) &&
      !node.closest('a,button,[role="button"],time') && !node.querySelector('[dir="auto"]') &&
      !node.matches('[role="button"]') && !moreText.test(label(node)) &&
      !(node.querySelector('a[href]') && clean(node.textContent) === clean(node.querySelector('a[href]').textContent)));
    if (bodies.length !== 1) return [{text_raw:null}];
    const body = bodies[0].cloneNode(true);
    body.querySelectorAll('[role="button"],button').forEach(node => node.remove());
    let text = '';
    const walk = node => {
      if (node.nodeType === Node.TEXT_NODE) text += node.textContent;
      else if (node.nodeName === 'BR') text += '\n';
      else if (node.nodeName === 'IMG') text += node.getAttribute('alt') || '';
      else node.childNodes.forEach(walk);
    };
    walk(body);
    if (!window.__cmtSeen.has(el)) window.__cmtSeen.set(el,String(++window.__cmtSeq));
    const parent = el.parentElement?.closest(boundary);
    const parentLink = comments.includes(parent) ? own(parent,'a[href]').find(a => /[?&]comment_id=\d+/.test(a.href)) : null;
    return [{text_raw:text,permalink:link?.href || null,observation_id:window.__cmtSeen.get(el),
      is_reply:comments.includes(parent) || /^(reply|phản hồi)/i.test(el.getAttribute('aria-label') || ''),
      parent_permalink:parentLink?.href || null,
      created_at:own(el,'time[datetime]')[0]?.getAttribute('datetime') || null,
      truncated:own(el,'[role="button"],button').some(b => visible(b) && moreText.test(label(b)))}];
  });
}
