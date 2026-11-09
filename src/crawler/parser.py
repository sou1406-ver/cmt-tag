"""Conservative metadata parsing. Never synthesize Facebook identifiers."""
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


def facebook_url(url):
    if not isinstance(url, str):
        raise ValueError('Expected a URL string')
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in {
        'facebook.com', 'www.facebook.com', 'm.facebook.com', 'web.facebook.com'
    } or parts.username or parts.password:
        raise ValueError('Expected an HTTPS Facebook post URL')
    query = parse_qs(parts.query)
    allowed = {k: query[k][0] for k in ('story_fbid', 'id', 'fbid', 'v',
                                       'comment_id', 'reply_comment_id') if k in query}
    return urlunsplit(('https', 'www.facebook.com', parts.path.rstrip('/'),
                       urlencode(allowed), ''))


def post_id(url):
    url = facebook_url(url)
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    found = re.search(r'/(?:posts|videos|reel)/(\d+|pfbid[A-Za-z0-9]+)(?:/|$)', parts.path)
    return found[1] if found else next((query[k][0] for k in ('story_fbid', 'fbid', 'v')
                                        if k in query), None)


def comment_identity(url, source_url):
    """Only accept comment links belonging to the requested post."""
    try:
        url, source_url = facebook_url(url), facebook_url(source_url)
    except ValueError:
        return None, None, None
    a, b = urlsplit(url), urlsplit(source_url)
    pid, expected = post_id(url), post_id(source_url)
    if not ((pid and expected and pid == expected) or
            (a.path == b.path and parse_qs(a.query).get('story_fbid') ==
             parse_qs(b.query).get('story_fbid'))):
        return None, None, None
    q = parse_qs(a.query)
    cid = q.get('reply_comment_id', q.get('comment_id', [None]))[0]
    if not cid or not cid.isdigit():
        return None, None, None
    parent = q.get('comment_id', [None])[0] if 'reply_comment_id' in q else None
    if parent and not parent.isdigit():
        parent = None
    return cid, parent, url


def observations(candidates, source_url):
    """Candidates contain only a specific comment body, never whole article text."""
    rows, errors = [], 0
    for item in candidates:
        if not isinstance(item.get('text_raw'), str):
            errors += 1
            continue
        cid, parent, permalink = comment_identity(item.get('permalink', ''), source_url)
        if item.get('permalink') and not permalink:
            errors += 1
            continue
        parent_id, _, _ = comment_identity(item.get('parent_permalink'), source_url)
        # aria-label comment/reply markers allow missing-ID comments; plain
        # post articles are not accepted by the DOM adapter.
        rows.append({
            'text_raw': item['text_raw'], 'comment_id': cid,
            'parent_comment_id': parent or parent_id,
            'comment_permalink': permalink, 'post_id': post_id(source_url),
            'comment_created_at': created_at(item.get('created_at')),
            'record_type': 'reply' if parent or item.get('is_reply') else 'comment',
            'extraction_status': 'truncated' if item.get('truncated') else 'complete',
            'dom_observation_id': item['observation_id'],
        })
    return rows, errors


def created_at(value):
    from datetime import datetime
    try:
        return value if value and datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None
