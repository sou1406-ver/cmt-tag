// Visible DOM only; no author fields, cookies or private API payloads.
(sourceUrl, action = 'read') => {
  const visible = el => !!el && !!el.getClientRects().length &&
    !el.closest('[hidden],[aria-hidden="true"]') && getComputedStyle(el).visibility !== 'hidden';
  const clean = text => String(text || '').replace(/\s+/g, ' ').trim();
  const identify = href => {
    try {
      const url = new URL(href, location.href);
      if (url.protocol !== 'https:' || !/(^|\.)facebook\.com$/i.test(url.hostname)) return null;
      const pathID = url.pathname.match(/\/(?:posts|permalink|videos|reel)\/(\d+|pfbid[A-Za-z0-9]+)(?:\/|$)/)?.[1];
      if (pathID) return pathID;
      // fbid on /photo.php or /photo/ identifies an attached photo, not
      // another source post. Do not let media links invalidate a post scope.
      if (/^\/(?:story|permalink)\.php$/.test(url.pathname))
        return url.searchParams.get('story_fbid') || url.searchParams.get('fbid');
      if (/^\/watch\/?$/.test(url.pathname)) return url.searchParams.get('v');
      return null;
    } catch { return null; }
  };
  const expected = identify(sourceUrl);
  const boundary = '[role="article"],[aria-label^="Bình luận của"],[aria-label^="Comment by"],'+
    '[aria-label^="Comment from"],[aria-label^="Reply"],[aria-label^="Phản hồi"]';
  const own = (el, selector) => [...el.querySelectorAll(selector)].filter(node => node.closest(boundary) === el);
  const marked = el => /^(comment|reply|bình luận|phản hồi)(\s|:|$)/i.test(el.getAttribute('aria-label') || '');
  const commentPermalink = a => /[?&](?:comment_id|reply_comment_id)=\d+/.test(a.href);
  const commentContainer = el => marked(el) || own(el,'a[href]').some(a=>commentPermalink(a)&&identify(a.href)===expected);
  const inComment = node => {
    for(let p=node.closest(boundary);p;p=p.parentElement?.closest(boundary))
      if(commentContainer(p)) return true;
    return false;
  };
  // A comment can cite another post. Its embedded link is comment content,
  // not a second post header that invalidates the surrounding source scope.
  const allIDs = el => new Set([...el.querySelectorAll('a[href]')].map(a=>identify(a.href)).filter(Boolean));
  const ids = el => new Set([...el.querySelectorAll('a[href]')].filter(a=>!inComment(a)).map(a => identify(a.href)).filter(Boolean));
  const matches = el => { const found = ids(el); return found.size === 1 && found.has(expected); };
  const current = identify(location.href);
  if (!expected || (current && current !== expected)) return action === 'read' ? [] : {status:'wrong_source'};
  const dialogs = [...document.querySelectorAll('[role="dialog"]')].filter(visible);
  const sourceDialogs=dialogs.filter(matches);
  let root = sourceDialogs.find(el=>!sourceDialogs.some(child=>child!==el&&el.contains(child)));
  if (!root) root = [...document.querySelectorAll('[role="article"]')].find(el => visible(el) &&
    !el.parentElement?.closest('[role="article"]') && matches(el) && !/[?&](?:comment_id|reply_comment_id)=/.test(
      [...el.querySelectorAll('a[href]')].find(a => identify(a.href))?.href || ''));
  if (!root && dialogs.length === 1 && current === expected && ids(dialogs[0]).size === 0) root = dialogs[0];
  // Retain the legacy comment-only layout: no dialogs/competing post header,
  // and every identifiable post link belongs to exactly the expected source.
  if (!root && !dialogs.length && (matches(document.body) ||
      (ids(document.body).size===0&&allIDs(document.body).size===1&&allIDs(document.body).has(expected))))
    root = document.querySelector('[role="main"]') || document.body;
  if (!root) return action === 'read' ? [] : {status:'missing_scope',
    diagnostics:{current_matches:current===expected,visible_dialogs:dialogs.length,
      dialog_source_counts:dialogs.map(el=>({distinct_post_ids:ids(el).size,has_expected:ids(el).has(expected)})),
      visible_articles:[...document.querySelectorAll('[role="article"]')].filter(visible).length}};
  const comments = [...root.querySelectorAll(boundary)].filter(el => {
    if(!visible(el)) return false;
    const permalinks=own(el,'a[href]').filter(commentPermalink);
    if(permalinks.length&&!permalinks.some(a=>identify(a.href)===expected)) return false;
    return marked(el)||permalinks.length>0;
  });
  const commentSet = new Set(comments);
  const insideComment = node => {
    for (let p=node.closest(boundary);p;p=p.parentElement?.closest(boundary))
      if (commentSet.has(p)) return true;
    return false;
  };
  if (action === 'inspect') return {status:'ready',comment_containers:comments.length};
  const all = /^(?:Tất cả (?:các )?bình luận|All comments)$/i;
  const filtered = /^(?:Phù hợp nhất|Liên quan nhất|Mới nhất|Most relevant|Newest|Top comments)$/i;
  const label = el => clean(el.innerText || el.getAttribute('aria-label'));
  if (action === 'sort') {
    const controls = [...root.querySelectorAll('button,[role="button"]')].filter(el => visible(el) &&
      !insideComment(el) && !el.closest('[role="menu"],[role="listbox"]'));
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
    (expansion.test(label(el)) || (insideComment(el) && moreText.test(label(el)))));
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
      // collect() has already read every currently loaded comment container.
      // Move to the end of that loaded range instead of rereading it in tiny
      // viewport steps. Do not jump past an unrendered/virtualized spacer.
      const viewportBottom=target===document.scrollingElement ? innerHeight :
        target.getBoundingClientRect().top+target.clientHeight;
      const loadedBottom=comments.filter(c=>target.contains(c)).reduce(
        (bottom,c)=>Math.max(bottom,c.getBoundingClientRect().bottom),viewportBottom);
      target.scrollBy(0,Math.max(180,target.clientHeight*.7,loadedBottom-viewportBottom));
      if (target.scrollTop > before) return {moved:true};
    }
    return {moved:false};
  }
  window.__cmtSeen ??= new WeakMap(); window.__cmtSeq ??= 0;
  const messageWrapper = node => {
    const wrapper=node.parentElement?.closest('[dir="auto"]');
    return wrapper && wrapper !== node.closest(boundary) && wrapper.closest(boundary)===node.closest(boundary) &&
      !wrapper.closest('a,[role="link"],button,[role="button"],time') &&
      !wrapper.querySelector('time,'+boundary) &&
      ![...wrapper.querySelectorAll('a[href]')].some(a=>/[?&](?:comment_id|reply_comment_id)=/.test(a.href)) ? wrapper : null;
  };
  return comments.flatMap(el => {
    const links = own(el,'a[href]');
    const commentLinks=links.filter(commentPermalink);
    const link=commentLinks.find(a=>identify(a.href)===expected);
    if (commentLinks.length&&!link) return [];
    let bodies = own(el,'[data-comment-body],[data-ad-preview="message"],[data-ad-comet-preview="message"]').filter(visible);
    if (!bodies.length) bodies = own(el,'[dir="auto"]').filter(node => visible(node) &&
      !node.closest('a,[role="link"],button,[role="button"],time') && !node.querySelector('[dir="auto"]') &&
      !node.matches('[role="button"]') && !moreText.test(label(node)) &&
      // A message may consist entirely of a tagged name/link plus emoji.
      // Accept that only inside its separate verified message wrapper.
      (!(node.querySelector('a[href]') && clean(node.textContent) === clean(node.querySelector('a[href]').textContent)) ||
        messageWrapper(node)));
    if (bodies.length > 1) {
      // Facebook renders one message as multiple paragraphs inside one dir=auto
      // span. Join only that verified message wrapper, never the whole article.
      const wrapper=messageWrapper(bodies[0]);
      if (wrapper && wrapper !== el && wrapper.closest(boundary)===el &&
          bodies.every(node=>wrapper.contains(node)) &&
          [...wrapper.querySelectorAll('a[href],[role="link"]')].every(a=>bodies.some(node=>node.contains(a))) &&
          [...wrapper.querySelectorAll('button,[role="button"]')].every(b=>moreText.test(label(b)))) bodies=[wrapper];
    }
    if (bodies.length !== 1) return [{text_raw:null,parse_error_reason:bodies.length?'ambiguous_body':'missing_body',
      candidate_shapes:bodies.map(node=>({tag:node.tagName,chars:node.textContent.length,
        has_link:!!node.querySelector('a[href]'),has_button:!!node.querySelector('button,[role="button"]')}))}];
    const body = bodies[0].cloneNode(true);
    body.querySelectorAll('[role="button"],button,time,script,style,[hidden],[aria-hidden="true"],'+boundary)
      .forEach(node => node.remove());
    // Only use an image alt as text when it is an actual Unicode emoji
    // sequence. Never turn an attachment's generated caption into a comment.
    const emojiAlt = value => /^(?:[\p{Extended_Pictographic}\p{Emoji_Presentation}\p{Regional_Indicator}\p{Emoji_Modifier}\uFE0E\uFE0F\u200D\u{E0020}-\u{E007F}]|[0-9#*]\uFE0F?\u20E3)+$/u.test(value);
    const accountLink = node => {
      if (!node.matches?.('a[href],[role="link"][href]')) return false;
      try {
        const u=new URL(node.getAttribute('href'),document.baseURI);
        if (u.protocol!=='https:' || !/(^|\.)facebook\.com$/i.test(u.hostname) ||
            u.searchParams.has('comment_id') || u.searchParams.has('reply_comment_id')) return false;
        if (u.pathname==='/profile.php') return /^\d+$/.test(u.searchParams.get('id')||'');
        if (/\.php$/i.test(u.pathname)) return false;
        if (/^\/people\/[^/]+\/\d+\/?$/.test(u.pathname)) return true;
        if (/^\/groups\/[A-Za-z0-9._-]+\/user\/\d+\/?$/.test(u.pathname)) return true;
        // A Facebook identity link can refer to a person or page. Strip only
        // that linked mention, never guess names from capitalized plain text.
        return /^\/[A-Za-z0-9.]+\/?$/.test(u.pathname) &&
          !/^\/(?:photo|photos|watch|reel|reels|groups|events|pages|hashtag|share|stories|login|help|marketplace|about|privacy|settings|search|gaming|friends|notifications)\/?$/i.test(u.pathname);
      } catch { return false; }
    };
    const linkKind = node => {
      if (!node.matches?.('a,[role="link"]')) return null;
      if (accountLink(node)) return 'mention';
      const href=node.getAttribute('href');
      if (!href || href.startsWith('#')) return 'ambiguous';
      try {
        const u=new URL(href,document.baseURI);
        if (!['http:','https:'].includes(u.protocol)) return 'ambiguous';
        if (!/(^|\.)facebook\.com$/i.test(u.hostname)) return 'url';
        if (/^\/hashtag\/[^/]+\/?$/.test(u.pathname)) return null;
        if (identify(u.href) || /^\/(?:l\.php|photo(?:\.php)?|photos|share|watch|reels?|events)(?:\/|$)/i.test(u.pathname) ||
            /^\/groups\/[A-Za-z0-9._-]+\/?$/.test(u.pathname)) return 'url';
      } catch { /* Keep ambiguous link text for review. */ }
      return 'ambiguous';
    };
    // Strip explicit URL tokens only; surrounding prose/punctuation is retained.
    const stripURLs = value => {
      let count=0;
      const text=value.replace(/(?:https?:\/\/|\bwww\.)[^\s<>"'\p{Extended_Pictographic}]+/giu, token => {
        let url=token,suffix='';
        const expression=url.match(/(?::[)(]+|:-[)(]+|=[)(]+|:v)$/i)?.[0];
        if (expression) { suffix=expression;url=url.slice(0,-expression.length); }
        while (/[.,!?;:…]$/.test(url) || [')',']','}'].some(c => url.endsWith(c) &&
            url.split(c).length>url.split({')':'(',']':'[','}':'{'}[c]).length)) {
          suffix=url.slice(-1)+suffix; url=url.slice(0,-1);
        }
        try {
          const parsed=new URL(/^www\./i.test(url)?'https://'+url:url);
          if (!parsed.hostname.includes('.')) return token;
        } catch { return token; }
        count++; return suffix;
      });
      return {text,count};
    };
    const renderText = mode => {
      let text='',mentions=0,media=0,urls=0,removed=false;
      const reasons=new Set();
      const walk=node=>{
        if (node.nodeType===Node.TEXT_NODE) {
          let value=node.textContent;
          // Remove only a colon separator immediately after a removed mention.
          // Never strip the ':' from :)), :):), :-) or ordinary '-' prose.
          if (removed) value=value.replace(/^\s*:(?=\s)/u,'');
          if (value.trim()) removed=false;
          text+=value;
        }
        else if (node.nodeName==='BR') text+='\n';
        else if (node.nodeName==='IMG') {
          const alt=node.getAttribute('alt')||'';
          if (emojiAlt(alt)) text+=alt; else media++;
        } else if (mode!=='raw' && accountLink(node)) {
          mentions++; removed=true;if (text && !/\s$/.test(text)) text+=' ';
        }
        else if (mode==='clean' && linkKind(node)==='url') {
          urls++;if (text && !/\s$/.test(text)) text+=' ';
        }
        else {
          if (mode==='clean' && linkKind(node)==='ambiguous') reasons.add('ambiguous_link');
          if (['DIV','P'].includes(node.nodeName) && text && !text.endsWith('\n')) text+='\n';
          node.childNodes.forEach(walk);
        }
      };
      walk(body);
      if (mode==='clean') {
        const stripped=stripURLs(text);text=stripped.text;urls+=stripped.count;
        if (media) reasons.add('non_text_media');
      }
      if (mode==='clean' || mentions) text=text.replace(/[ \t]{2,}/g,' ').trim();
      return {text,mentions,media,urls,reasons:[...reasons]};
    };
    const original=renderText('raw'),withoutMentions=renderText('mentions'),cleaned=renderText('clean');
    if (!window.__cmtSeen.has(el)) window.__cmtSeen.set(el,String(++window.__cmtSeq));
    const parent = el.parentElement?.closest(boundary);
    const parentLink = commentSet.has(parent) ? own(parent,'a[href]').find(a => /[?&]comment_id=\d+/.test(a.href)) : null;
    return [{text_raw:original.text,text_without_mentions:withoutMentions.text,
      mention_count:withoutMentions.mentions,non_text_media_count:original.media,text_extraction_version:'dom_text_v3',
      text_clean:cleaned.text,url_count:cleaned.urls,clean_review_reasons:cleaned.reasons,
      clean_status:cleaned.reasons.length?'REVIEW':cleaned.text.trim()?'KEEP':'EXCLUDE',
      permalink:link?.href || null,observation_id:window.__cmtSeen.get(el),
      is_reply:commentSet.has(parent) || /^(reply|phản hồi)/i.test(el.getAttribute('aria-label') || ''),
      parent_permalink:parentLink?.href || null,
      created_at:own(el,'time[datetime]')[0]?.getAttribute('datetime') || null,
      truncated:own(el,'[role="button"],button').some(b => visible(b) && moreText.test(label(b)))}];
  });
}
