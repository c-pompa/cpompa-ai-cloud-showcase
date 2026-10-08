"""Snapshot 30-day activity for the project cards into repo-activity.json.

The GitLab repos are private, so the page can't query them live; run this locally
(uses your `glab` and `gh` logins) and commit the JSON. Only counts and dates are
written, never repo names, commit messages, or URLs.
"""
import json
import re
import subprocess
import urllib.parse
from datetime import datetime, timedelta, timezone

DAYS = 30
# Card order matches the project cards on the page.
CARDS = [
    {'gitlab': [20]},                               # cpompa-ai-cloud
    {'gitlab': [16, 17, 9, 15, 11, 8, 30],          # Plugins: fork-upgrader, router-studio, metrics-dash, lan-cluster, model-router, desktop-iac, operations
     'github_prs': 'NousResearch/hermes-agent'},    # and their PRs to Hermes Agent (upstream, public)
    {'gitlab': [28, 24, 27]},                       # HIP: program root, swarm-kit, self-evolution (fork 4 left out: upstream history)
    {'gitlab': [23, 13, 14, 22]},                   # LLM fleet: ai-cluster, infra, dsv4-router, compaction-test
]

now = datetime.now(timezone.utc)
since = (now - timedelta(days=DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')


def api(path):
    out = subprocess.run(['glab', 'api', '--paginate', '--output', 'ndjson', path],
                         capture_output=True, text=True, check=True).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def utc(iso):
    return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def day_index(iso):
    return DAYS - 1 - (now - datetime.fromisoformat(iso.replace('Z', '+00:00'))).days


def gitlab_card(ids):
    daily, last, merged, passed, failed = [0] * DAYS, None, 0, 0, 0
    for pid in ids:
        # all=true ignores paging on GitLab, so walk each recently active branch and dedupe
        commits = {}
        for br in api(f'projects/{pid}/repository/branches?per_page=100'):
            if br['commit']['created_at'] < since:
                continue
            ref = urllib.parse.quote(br['name'], safe='')
            for c in api(f'projects/{pid}/repository/commits?ref_name={ref}&since={since}&per_page=100'):
                commits[c['id']] = utc(c['created_at'])
        for created in commits.values():
            i = day_index(created)
            if 0 <= i < DAYS:
                daily[i] += 1
            last = max(last or '', created)
        merged += sum(1 for m in api(f'projects/{pid}/merge_requests?state=merged&updated_after={since}&per_page=100')
                      if m['merged_at'] and m['merged_at'] >= since)
        for p in api(f'projects/{pid}/pipelines?updated_after={since}&per_page=100'):
            passed += p['status'] == 'success'
            failed += p['status'] == 'failed'
    return {'repos': len(ids), 'daily': daily, 'commits': sum(daily), 'last_commit': last,
            'mrs_merged': merged, 'pipelines': passed + failed,
            'pass_rate': round(100 * passed / (passed + failed), 1) if passed + failed else None}


def github_card(repo):
    out = subprocess.run(['gh', 'search', 'prs', '--author', '@me', '--repo', repo, '--limit', '100',
                          '--json', 'state,createdAt'], capture_output=True, text=True, check=True).stdout
    prs = json.loads(out)
    daily = [0] * DAYS
    for p in prs:
        i = day_index(p['createdAt'])
        if 0 <= i < DAYS:
            daily[i] += 1
    return {'daily': daily, 'prs_open': sum(p['state'] == 'open' for p in prs),
            'prs_merged': sum(p['state'] == 'merged' for p in prs), 'prs_total': len(prs),
            'last_pr': max((p['createdAt'] for p in prs), default=None)}


def review_stats():
    # All time, every project. GitLab approval rules aren't enabled on this instance, so a merge
    # by a human account is the human sign-off. The Hermes review bot posts MR notes tagged
    # "<!-- hermes-review-bot sha=... -->" with a "VERDICT: looks-good|concerns" line.
    humans = {u['id'] for u in api('users?humans=true&per_page=100')}
    s = dict(mrs=0, human_merged=0, bot_mrs=0, bot_reviews=0, re_reviews=0, looks_good=0, concerns=0,
             fixed_after_concerns=0, human_followups=0)
    for p in api('projects?membership=true&per_page=100'):
        for m in api(f"projects/{p['id']}/merge_requests?state=all&per_page=100"):
            s['mrs'] += 1
            s['human_merged'] += m['state'] == 'merged' and (m['merged_by'] or {}).get('id') in humans
            if not m['user_notes_count']:
                continue
            notes = [n for n in api(f"projects/{p['id']}/merge_requests/{m['iid']}/notes?per_page=100&sort=asc")
                     if not n['system']]
            bot = [n for n in notes if 'hermes-review-bot' in n['body']]
            if not bot:
                continue
            verdicts = [v.group(1) for n in bot if (v := re.search(r'VERDICT:\s*([a-z-]+)', n['body']))]
            shas = {h.group(1) for n in bot if (h := re.search(r'sha=([0-9a-f]+)', n['body']))}
            s['bot_mrs'] += 1
            s['bot_reviews'] += len(bot)
            s['re_reviews'] += max(0, len(shas) - 1)   # reviewed again after new commits were pushed
            s['looks_good'] += verdicts.count('looks-good')
            s['concerns'] += verdicts.count('concerns')
            s['fixed_after_concerns'] += 'concerns' in verdicts and verdicts[-1] == 'looks-good'
            s['human_followups'] += any('hermes-review-bot' not in n['body'] and n['created_at'] > bot[0]['created_at']
                                        for n in notes)
    return s


snapshot = {'generated': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'days': DAYS,
            'cards': [{**gitlab_card(c['gitlab']), **({k: v for k, v in github_card(c['github_prs']).items() if k != 'daily'} if 'github_prs' in c else {})} for c in CARDS],
            'reviews': review_stats()}
with open('repo-activity.json', 'w') as f:
    json.dump(snapshot, f)
print(json.dumps(snapshot, indent=1))
