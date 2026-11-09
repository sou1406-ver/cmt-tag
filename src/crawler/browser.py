"""Bounded visible-DOM collection. No private API or access-control bypass."""
import re
import time
from pathlib import Path
from uuid import uuid4

from .parser import observations

EXTRACT = Path(__file__).with_name('dom.js').read_text(encoding='utf-8')
BLOCKED = re.compile(r'captcha|checkpoint|temporarily blocked|tạm thời bị chặn|'
                     r'content isn.t available|nội dung này hiện không', re.I)


def dom(page,source,action='read'):
    return page.execute_script('return ('+EXTRACT+')(arguments[0],arguments[1]);',source,action)


def access_barrier(page):
    if any(part in page.current_url for part in ('/login','/checkpoint','/captcha','/two_step_verification')):
        return True
    return any(BLOCKED.search(el.text) for el in page.find_elements('css selector','h1,h2,[role="alert"]'))


def collect(page, store, post):
    """NAVIGATE → WAIT → EXPAND → EXTRACT → SCROLL → SETTLE → FINISH.

    Success means bounded visible DOM exhausted, never all Facebook comments.
    """
    from selenium.webdriver.support.ui import WebDriverWait
    cfg = store.config
    deadline = time.monotonic() + cfg['post_timeout']
    session = uuid4().hex
    start_count = store.post_counts[post['post_url']]
    if start_count >= cfg['max_comments']:
        return 'partial', 'comment_limit', []
    trace, pending, idle = ['NAVIGATE'], {}, 0
    page.set_page_load_timeout(cfg['wait_ms']/1000)
    page.get(post['post_url'])
    trace.append('WAIT')
    if access_barrier(page):
        return 'blocked', 'access_barrier', trace
    try:
        WebDriverWait(page,min(cfg['wait_ms']/1000,max(.001,deadline-time.monotonic())),poll_frequency=.1).until(
            lambda driver:dom(driver,post['post_url'],'inspect').get('status')=='ready')
    except Exception:
        if access_barrier(page): return 'blocked','access_barrier',trace
        probe=dom(page,post['post_url'],'inspect')
        store.append('errors.jsonl',{'code':'scope_diagnostic','post_url':post['post_url'],
                     'scope_status':probe.get('status'),'diagnostics':probe.get('diagnostics',{})})
        return 'partial', 'post_scope_not_found', trace
    reason, status = 'round_limit', 'partial'
    for _ in range(cfg['max_rounds']):
        if time.monotonic() >= deadline:
            reason = 'time_limit'
            break
        if access_barrier(page):
            status, reason = 'blocked', 'access_barrier'
            break
        scope=dom(page,post['post_url'],'inspect')
        if scope.get('status')!='ready':
            reason=scope.get('status','missing_scope'); break
        trace.append('SORT')
        sorting=dom(page,post['post_url'],'sort')
        if sorting.get('status')=='failed':
            reason='comment_sort_failed'; break
        if sorting.get('status') in ('opening','selecting','waiting'):
            if sorting.get('element') is not None:
                try: sorting['element'].click()
                except Exception: pass
            try:
                WebDriverWait(page,min(cfg['settle_ms']/1000,max(.001,deadline-time.monotonic())),poll_frequency=.2).until(
                    lambda driver:dom(driver,post['post_url'],'sort').get('status') not in (sorting['status'],'waiting'))
            except Exception: pass
            # Re-resolve and confirm on the next bounded round; a menu option
            # being visible is not proof the selected filter changed.
            continue
        trace.append('SORT_'+sorting.get('status','unavailable').upper())
        trace.append('EXPAND')
        clicked = 0
        # Never click arbitrary page links. Restrict to comment containers or
        # comment-list buttons, with exact localized action labels.
        buttons = dom(page,post['post_url'],'buttons')
        for button in buttons[:cfg['max_actions']]:
            if time.monotonic() >= deadline:
                break
            try:
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    clicked += 1
            except Exception:
                # Fixed action budget; failure is reported via partial settle.
                pass
        trace.append('EXTRACT')
        candidates = dom(page,post['post_url'])
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
        scrolled=dom(page,post['post_url'],'scroll').get('moved',False)
        trace.append('SETTLE')
        # Explicit poll for DOM changes, bounded even for silent/no-comment pages.
        before = len(candidates)
        try:
            article_count=len(page.find_elements('css selector','[role="article"]'))
            WebDriverWait(page,min(cfg['settle_ms']/1000,max(.001,deadline-time.monotonic())),poll_frequency=.1).until(
                lambda driver:len(driver.find_elements('css selector','[role="article"]'))>article_count)
        except Exception:
            pass
        idle = idle+1 if not added and not clicked and not scrolled else 0
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
