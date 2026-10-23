"""Daily submission quotas shared by both intake bots."""
from __future__ import annotations

from datetime import date
from glob import glob

from core import json_doc
from core.ingest_common import INTAKE_REL

_STATE = None


def load_quota():
    """Read quota declaration, falling back to conservative (2, 20)."""
    try:
        with open(INTAKE_REL, encoding='utf-8') as f:
            data = json_doc.loads(f.read(), dict, what=INTAKE_REL)
        q = ((data.get('submission') or {}).get('quota') or {})
        per_author = int(q.get('per_author_per_day', 2))
        global_limit = int(q.get('global_per_day', 20))
        if per_author >= 1 and global_limit >= 1:
            return per_author, global_limit
    except Exception as exc:
        print(f'⚠ 投稿配额不可读（{exc}）：使用保守默认 2/20')
    return 2, 20


def _frontmatter_scalar(text, key):
    import re
    m = re.search(r'(?m)^%s:\s*(.+?)\s*$' % re.escape(key), text)
    return m.group(1).strip().strip('\'"') if m else ''


def daily_usage(day=None):
    """Count today's library entries as ({author: n}, total)."""
    target = day or date.today().isoformat()
    by_author = {}
    total = 0
    for path in glob('library/NF-*.md'):
        try:
            with open(path, encoding='utf-8') as fh:
                text = fh.read(4096)
        except OSError:
            continue
        if _frontmatter_scalar(text, 'generated') != target:
            continue
        author = _frontmatter_scalar(text, 'author').lower() or 'unknown'
        by_author[author] = by_author.get(author, 0) + 1
        total += 1
    return by_author, total


def reset_quota_state():
    global _STATE
    _STATE = None


def quota_denial(author):
    """Return a rejection reason, or empty when the submission may proceed."""
    global _STATE
    if _STATE is None:
        _STATE = daily_usage()
    by_author, total = _STATE
    per_author, global_limit = load_quota()
    who = str(author or 'unknown').strip().lower() or 'unknown'
    if by_author.get(who, 0) >= per_author:
        return '同一投稿人当日已达 %d 条上限' % per_author
    if total >= global_limit:
        return '全仓当日投稿已达 %d 条上限' % global_limit
    return ''


def record_quota(author):
    """Account for one accepted candidate; disk scan recovers failed retries."""
    global _STATE
    who = str(author or 'unknown').strip().lower() or 'unknown'
    if _STATE is None:
        _STATE = daily_usage()
    by_author, total = _STATE
    by_author[who] = by_author.get(who, 0) + 1
    _STATE = (by_author, total + 1)
