"""ARLIS HTML extraction and explicit revision-pair discovery; no AI dependency."""
import difflib
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ORIGIN = 'https://www.arlis.am'
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class SourceError(Exception):
    pass


class Node:
    def __init__(self, tag='', attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def has(self, name):
        return name in self.attrs.get('class', '').split()

    def nodes(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.nodes()

    def text(self):
        if self.tag in ('script','style'):
            return ''
        return ' '.join(' '.join(c.text() if isinstance(c, Node) else c for c in self.children).split())


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def act_url(value, latest=False):
    parsed = urllib.parse.urlsplit(urllib.parse.urljoin(ORIGIN, value))
    match = re.fullmatch(r'/hy/acts/(\d+)(?:/latest)?/?', parsed.path)
    if parsed.scheme != 'https' or parsed.hostname not in ('arlis.am','www.arlis.am') or not match:
        raise SourceError('Unexpected ARLIS act URL')
    return ORIGIN + '/hy/acts/' + match[1] + ('/latest' if latest else '')


def fetch(url, ajax=False):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('arlis.am','www.arlis.am'):
        raise SourceError('Only official ARLIS hosts are allowed')
    headers = {'User-Agent':'NovasolLawBot/0.2 (legal publication reader)'}
    if ajax:
        headers.update({'X-REQUESTED-WITH':'XMLHttpRequest','Accept':'application/json'})
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        if urllib.parse.urlsplit(response.url).hostname not in ('arlis.am','www.arlis.am'):
            raise SourceError('Unexpected redirect')
        data = response.read(8_000_001)
    if len(data) > 8_000_000:
        raise SourceError('Source exceeds extraction size limit')
    return data.decode('utf-8-sig')


def recent_cards(html):
    """Only actual recent-result cards, excluding permanent links to old codes."""
    result = {}
    for node in Tree(html).root.nodes():
        if not node.has('act-card__title'):
            continue
        link = next((n for n in node.nodes() if n.tag == 'a' and n.attrs.get('href')), None)
        if link:
            url = act_url(link.attrs['href'], latest=True)
            result[url] = link.text()
    if not result:
        raise SourceError('Recent publication cards not found; layout may have changed')
    return result


def document(html, url):
    root = Tree(html).root
    body = next((n for n in root.nodes() if n.attrs.get('id') == 'act_body'), None)
    title = next((n.text() for n in root.nodes() if n.tag == 'title'), '')
    if body is None or len(body.text()) < 100:
        raise SourceError('Legal act body missing or unreadable')
    paragraphs = [n.text() for n in body.nodes() if n.tag in ('p','li') and n.text()]
    text = '\n'.join(paragraphs) if paragraphs else body.text()
    metadata = {}
    for node in root.nodes():
        if node.has('act-info__item'):
            label = next((n.text() for n in node.nodes() if n.has('act-info__label')), '')
            value = next((n.text() for n in node.nodes() if n.has('act-info__value')), '')
            if label:
                metadata[label] = value
    # Only comparison controls inside the "amends these acts" tab qualify.
    # Other history tabs can pair amending acts with consolidations instead.
    pairs = []
    for tab in root.nodes():
        if not tab.has('nested-tab-container') or 'Փոփոխություններ է կատարել հետևյալ ակտերում' not in tab.text():
            continue
        for node in tab.nodes():
            match = re.fullmatch(r'/hy/acts/(\d+)/compare/(\d+)', node.attrs.get('data-request-url',''))
            if match:
                pair = (ORIGIN + '/hy/acts/' + match[1], ORIGIN + '/hy/acts/' + match[2])
                if pair not in pairs:
                    pairs.append(pair)
    return {'url':act_url(url), 'title':title, 'text':text, 'metadata':metadata, 'revision_pairs':pairs}


def evidence(url, loader=fetch, max_pairs=3):
    act = document(loader(url), url)
    comparisons = []
    for old_url, new_url in act['revision_pairs'][:max_pairs]:
        old = document(loader(old_url), old_url)
        new = document(loader(new_url), new_url)
        # A comparison link is source evidence for the pairing, but not proof of
        # every provision's commencement. Effective dates remain separate facts.
        changes = []
        old_lines, new_lines = old['text'].splitlines(), new['text'].splitlines()
        for tag, a, b, c, d in difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
            if tag != 'equal':
                changes.append({'operation':tag, 'before':old_lines[a:b], 'after':new_lines[c:d]})
        comparisons.append({'before_url':old_url,'after_url':new_url,
                            'before_metadata':old['metadata'],'after_metadata':new['metadata'],
                            'changes':changes})
    act['comparisons'] = comparisons
    act['comparison_complete'] = len(act['revision_pairs']) <= max_pairs
    return act


def weekly_files(section, loader=fetch):
    """Read the site's own public AJAX listing; PDFs are counted, not analyzed."""
    result, previous = {}, None
    for page in range(1, 11):
        url = ORIGIN + f'/hy/releases/{int(section)}/files?page={page}'
        data = json.loads(loader(url, ajax=True))
        if data.get('status') != 0 or not isinstance(data.get('html'),str):
            raise SourceError('Official publication listing unavailable')
        html = data['html']
        if html == previous:
            raise SourceError('Repeated pagination; coverage not established')
        previous = html
        root = Tree(html).root
        for node in root.nodes():
            href = node.attrs.get('href','')
            if node.tag == 'a' and re.fullmatch(r'/releases/files/\d+/[a-f0-9]+', href):
                result[ORIGIN + href] = node.text()
        pages = [int(n.attrs['value']) for n in root.nodes() if n.tag == 'vx-select' and n.attrs.get('value','').isdigit()]
        # The site's selector supplies a JSON options list identifying all pages.
        maximum = 1
        for node in root.nodes():
            if node.tag == 'vx-select' and node.attrs.get('name') == 'page-selector':
                options = json.loads(node.attrs.get('options','[]'))
                maximum = max([int(x['value']) for x in options] or [1])
        if page >= maximum:
            return result
    raise SourceError('Official listing exceeds configured 10-page limit')
