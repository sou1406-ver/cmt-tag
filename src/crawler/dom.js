// Loaded only against the page the user has opened. No network interception,
// profile links, author names, cookies, tokens, or HTML dumps are collected.
() => {
  window.__cmtSeen ??= new WeakMap();
  window.__cmtSeq ??= 0;
  const articles = [...document.querySelectorAll('[role="article"]')];
  const own = (el, selector) => [...el.querySelectorAll(selector)]
    .filter(x => x.closest('[role="article"]') === el);
  return articles.flatMap(el => {
    const links = own(el, 'a[href]');
    const link = links.find(x => /[?&](comment_id|reply_comment_id)=\d+/.test(x.href));
    const label = el.getAttribute('aria-label') || '';
    const marked = /^(comment|reply|bình luận|phản hồi)(\s|:|$)/i.test(label);
    if (!link && !marked) return []; // A post body is never a comment.
    const bodies = own(el, '[data-ad-preview="message"], [data-comment-body], div[dir="auto"][style*="text-align"]');
    // Ambiguity is visible as missing extraction, never concatenate UI/author.
    if (bodies.length !== 1) return [{text_raw:null}];
    const body = bodies[0].cloneNode(true);
    body.querySelectorAll('[role="button"],button').forEach(x => x.remove());
    let text = '';
    const walk = node => {
      if (node.nodeType === Node.TEXT_NODE) text += node.textContent;
      else if (node.nodeName === 'BR') text += '\n';
      else if (node.nodeName === 'IMG') text += node.getAttribute('alt') || '';
      else node.childNodes.forEach(walk);
    };
    walk(body);
    if (!window.__cmtSeen.has(el)) window.__cmtSeen.set(el, String(++window.__cmtSeq));
    const time = own(el, 'time[datetime]')[0];
    const parent = el.parentElement?.closest('[role="article"]');
    const parentLink = parent ? own(parent, 'a[href]').find(x => /[?&]comment_id=\d+/.test(x.href)) : null;
    return [{text_raw:text, permalink:link?.href || null,
      observation_id:window.__cmtSeen.get(el),
      is_reply:!!parent || /^(reply|phản hồi)/i.test(label),
      parent_permalink:parentLink?.href || null,
      created_at:time?.getAttribute('datetime') || null,
      truncated:own(el, '[role="button"],button').some(x => /^(see more|xem thêm)$/i.test(x.textContent.trim()))}];
  });
}
