#!/usr/bin/env python3
"""Build cpompa.com from threejs-lab.html into a folder (default: ~/www/cpompa-com-staging).

  index.html            the map alone: no portfolio text in the page or its source
  collab/index.html     the full page, unlisted and tagged noindex (it is linked from nowhere)
  collab/repo-activity.json
  robots.txt            turns AI crawlers away from the whole site; never names /collab/
"""
import pathlib, re, shutil, sys

HERE = pathlib.Path(__file__).parent
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path.home() / 'www/cpompa-com-staging')
src = (HERE / 'threejs-lab.html').read_text()


def swap(s, old, new):
    assert s.count(old) == 1, old[:70]
    return s.replace(old, new)


def cut(s, start, end, new):   # replace from start marker through end marker
    a = s.index(start); b = s.index(end, a) + len(end)
    assert s.count(start) == 1
    return s[:a] + new + s[b:]


# collab: the page as it is, kept out of search and AI indexes
collab = swap(src, '<title>Three.js lab — topographic</title>',
              '<title>Christian Pompa</title>\n<meta name="robots" content="noindex, nofollow, noarchive, nosnippet, noimageindex, noai, noimageai">')

# home: the same map with every word taken out of the source, the cards kept as empty boxes so the layout code still runs
years = re.findall(r"\{ year: '([^']+)'", src)
stats = re.search(r'\n  stats: .*?\n(?=\};)', src, re.S).group(0)
home = swap(src, '<title>Three.js lab — topographic</title>', '<title>cpompa.com</title>')
home = cut(home, '// Content mirrors index.html', '\n};',
           "const DATA = {\n  name: '', motto: '', role: '', about: '', links: [],\n"
           "  projects: Array.from({ length: 4 }, () => ({ title: '', sub: '', body: '', tags: [] })),\n"
           f"  climb: {years!r}.map(year => ({{ year, tag: '', title: '', body: '' }})),{stats}}};")
home = cut(home, "document.getElementById('content').innerHTML = `", "</section>`;",
           """document.getElementById('content').innerHTML = `
  <section class="screen wrap"><div class="col panel hero"><a href="#finale" id="to-contact"></a></div></section>
  <section class="wrap"><div class="col stack climb"><div class="panel head"></div>
    <div class="trek"><div class="reel">${DATA.climb.map((c, i) => `<article class="panel" id="step-${i}"></article>`).join('')}</div></div>
    <div class="trek-room"></div></div></section>
  <section class="wrap"><div class="col stack peaks"><div class="panel head"></div><div class="panel" id="review-loop" hidden></div>
    ${DATA.projects.map((p, i) => `<article class="panel" id="peak-${i}"></article>`).join('')}</div></section>
  <section class="wrap finale" id="finale"><div class="col"><div class="panel" id="contact"><div class="wp"><svg width="14" height="14"></svg></div></div></div>
    <footer class="sheet"><span id="coords"></span><a href="#" id="to-top"></a></footer></section>`;""")
home = cut(home, '// Repo activity snapshot', '// no snapshot (e.g. opened from file://): cards render without it', '')
home = swap(home, '</style>', '  #content,#markers,.dock,#boot{visibility:hidden}#tilt,#trailend,#trailshade{display:none}   /* home: the map alone, no tilt-shift, no trail to a card */\n</style>')
home = swap(home, "addEventListener('wheel', e => {\n", "addEventListener('wheel', e => {\n  return;   // home: plain scrolling, no snapping between sections\n")
home = swap(home, 'function panAt(sy) {\n', 'function panAt(sy) {\n  return PAN * sy;   // home: the map scrolls straight through, never held on the climb\n')
home = swap(home, 'if (!placeSaved || placeMine) locate(false);', '')   # no location prompt on a page with no controls
for words in ('Christian', 'mailto', 'linkedin', 'Senior DevOps', 'Counter-Strike', 'Hermes desktop', 'Always looking'):   # only code comments may remain
    assert words not in home, words

ROBOTS = """# AI crawlers and training scrapers: none of this site
User-agent: GPTBot
User-agent: ChatGPT-User
User-agent: OAI-SearchBot
User-agent: ClaudeBot
User-agent: Claude-User
User-agent: Claude-SearchBot
User-agent: anthropic-ai
User-agent: CCBot
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: PerplexityBot
User-agent: Perplexity-User
User-agent: Bytespider
User-agent: Amazonbot
User-agent: meta-externalagent
User-agent: FacebookBot
User-agent: cohere-ai
User-agent: Diffbot
User-agent: YouBot
User-agent: Timpibot
User-agent: ImagesiftBot
Disallow: /

User-agent: *
Allow: /
"""

(OUT / 'collab').mkdir(parents=True, exist_ok=True)
(OUT / 'index.html').write_text(home)
(OUT / 'collab/index.html').write_text(collab)
shutil.copy(HERE / 'repo-activity.json', OUT / 'collab/repo-activity.json')
(OUT / 'robots.txt').write_text(ROBOTS)
print('built', OUT)
