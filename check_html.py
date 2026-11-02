"""Read HTML acts directly. No PDF, AI, Telegram or database writes."""
import sys
from arlis_source import ORIGIN, act_url, fetch, recent_cards, evidence


def main(args=None):
    args = sys.argv[1:] if args is None else args
    if len(args) > 1:
        raise ValueError('Use: check_html.py [official act URL]')
    if args:
        urls = [act_url(args[0], latest=True)]
        print('Discovery: explicitly supplied official act URL', flush=True)
    else:
        cards = recent_cards(fetch(ORIGIN + '/hy/'))
        print('Recent HTML cards:',len(cards),flush=True)
        urls = list(cards)[:3]
    failures = 0
    for url in urls:
        try:
            item = evidence(url)
            print('Act:',url,flush=True)
            print('Legal body characters:',len(item['text']),flush=True)
            print('Metadata fields:',len(item['metadata']),flush=True)
            print('Official comparison pairs:',len(item['revision_pairs']),flush=True)
            print('Comparison complete:',item['comparison_complete'],flush=True)
            print('Changed blocks:',sum(len(x['changes']) for x in item['comparisons']),flush=True)
            if not item['revision_pairs']:
                print('Before/after comparison: NOT ESTABLISHED',flush=True)
        except Exception as exc:
            failures += 1
            print('Act failed:',url,type(exc).__name__,flush=True)
    print('Scope: at most three recent cards or one supplied URL; NOT complete daily coverage.')
    print('PDF requests: 0; AI calls: 0; Telegram posts: 0; database writes: 0.')
    print('Collection setting unchanged.')
    return 1 if failures else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('HTML check failed:',type(exc).__name__)
        raise SystemExit(1)
