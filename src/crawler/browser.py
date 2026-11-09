"""Bounded visible-DOM collection. No private API or access-control bypass."""
import re
import time
from pathlib import Path
from uuid import uuid4

from .parser import observations

EXTRACT = Path(__file__).with_name('dom.js').read_text(encoding='utf-8')
MORE = re.compile(r'^(?:See more|Xem thêm|View (?:\d+ )?more comments|'
                  r'View previous comments|Xem (?:thêm |các )?bình luận(?: trước)?|'
                  r'View (?:\d+ )?(?:more )?repl(?:y|ies)|'
                  r'Xem (?:thêm )?(?:\d+ )?(?:phản hồi|câu trả lời))$', re.I)
BLOCKED = re.compile(r'captcha|checkpoint|temporarily blocked|tạm thời bị chặn|'
                     r'content isn.t available|nội dung này hiện không', re.I)


def access_barrier(page):
    if any(part in page.url for part in ('/login','/checkpoint','/captcha')):
        return True
    return any(BLOCKED.search(text) for text in page.locator('h1,h2,[role="alert"]').all_text_contents())


def collect(page, store, post):
    """NAVIGATE → WAIT → EXPAND → EXTRACT → SCROLL → SETTLE → FINISH.

    Success means bounded visible DOM exhausted, never all Facebook comments.
    """
    cfg = store.config
    deadline = time.monotonic() + cfg['post_timeout']
    session = uuid4().hex
    start_count = store.post_counts[post['post_url']]
    if start_count >= cfg['max_comments']:
        return 'partial', 'comment_limit', []
    trace, pending, idle = ['NAVIGATE'], {}, 0
    page.goto(post['post_url'], wait_until='domcontentloaded', timeout=cfg['wait_ms'])
    trace.append('WAIT')
    if access_barrier(page):
        return 'blocked', 'access_barrier', trace
    try:
        page.locator('[role="article"]').first.wait_for(timeout=min(cfg['wait_ms'], max(1,int((deadline-time.monotonic())*1000))))
    except Exception:
        return 'partial', 'comment_dom_not_found', trace
    reason, status = 'round_limit', 'partial'
    for _ in range(cfg['max_rounds']):
        if time.monotonic() >= deadline:
            reason = 'time_limit'
            break
        if access_barrier(page):
            status, reason = 'blocked', 'access_barrier'
            break
        trace.append('EXPAND')
        clicked = 0
        # Never click arbitrary page links. Restrict to comment containers or
        # comment-list buttons, with exact localized action labels.
        buttons = page.locator('[role="article"] [role="button"], [role="article"] button').filter(has_text=MORE)
        for i in range(min(buttons.count(), cfg['max_actions'])):
            if time.monotonic() >= deadline:
                break
            try:
                button = buttons.nth(i)
                if button.is_visible():
                    button.click(timeout=min(cfg['wait_ms'], max(1,int((deadline-time.monotonic())*1000))))
                    clicked += 1
            except Exception:
                # Fixed action budget; failure is reported via partial settle.
                pass
        trace.append('EXTRACT')
        candidates = page.evaluate(EXTRACT)
        parsed, errors = observations(candidates, post['post_url'])
        if errors:
            store.append('errors.jsonl', {'code':'parse_error','count':errors,'post_url':post['post_url']})
        added = 0
        for row in parsed:
            count = store.post_counts[post['post_url']]
            if count >= cfg['max_comments']:
                reason = 'comment_limit'
                break
            if row['extraction_status']=='truncated':
                pending[row['comment_id'] or row['dom_observation_id']] = row
            else:
                pending.pop(row['comment_id'] or row['dom_observation_id'],None)
                added += store.add(row,post,session)
        if reason == 'comment_limit':
            break
        trace.append('SCROLL')
        # Scroll nested dialog/list viewport when Facebook uses one, then page.
        page.evaluate("""() => {
          const nodes=[...document.querySelectorAll('[role="dialog"] *')];
          const scroll=nodes.filter(n=>n.scrollHeight>n.clientHeight+50 &&
            ['auto','scroll'].includes(getComputedStyle(n).overflowY));
          scroll.forEach(n=>n.scrollBy(0,n.clientHeight));
          window.scrollBy(0,window.innerHeight);
        }""")
        trace.append('SETTLE')
        # Explicit poll for DOM changes, bounded even for silent/no-comment pages.
        before = len(candidates)
        try:
            page.wait_for_function("n => document.querySelectorAll('[role=article]').length > n",
                                   arg=page.locator('[role="article"]').count(),
                                   timeout=min(cfg['settle_ms'], max(1,int((deadline-time.monotonic())*1000))))
        except Exception:
            pass
        idle = idle+1 if not added and not clicked else 0
        if idle >= cfg['idle_rounds']:
            status = 'success' if parsed and not pending and not errors else 'partial'
            reason = 'visible_dom_exhausted' if parsed else 'no_recognized_comments'
            break
    for row in pending.values():
        if store.post_counts[post['post_url']] < cfg['max_comments']:
            store.add(row,post,session)
    if pending and status=='success':
        status, reason = 'partial','truncated_comments'
    return status, reason, trace + ['FINISH']


def run_posts(store, page, collector=collect, posts=None, finalize=True):
    done = {p['post_url'] for p in store.posts if p['status']=='success'}
    try:
        for post in (store.config['posts'] if posts is None else posts)[:store.config['max_posts']]:
            if post['post_url'] in done:
                continue
            for attempt in range(store.config['retries']+1):
                try:
                    status, reason, trace = collector(page,store,post)
                    store.finish_post(post,status,reason,state_trace=trace,attempt=attempt+1)
                    break
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    # Exception strings can contain URL query secrets or page text.
                    store.append('errors.jsonl', {'code':'browser_error','error_type':type(exc).__name__,
                                 'post_url':post['post_url'],'attempt':attempt+1})
                    if attempt == store.config['retries']:
                        store.finish_post(post,'failed','retry_exhausted',attempt=attempt+1)
        return store.finish() if finalize else None
    except BaseException:
        store.checkpoint('interrupted')
        raise
