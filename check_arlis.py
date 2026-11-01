"""No API key needed. No AI calls, Telegram messages or database changes."""
import json
from arlis_source import ORIGIN, fetch, recent_cards, evidence, weekly_files


def main():
    cards = recent_cards(fetch(ORIGIN + '/hy/'))
    print('Recent publication cards:', len(cards))
    print('Permanent code shortcuts excluded: YES')
    url = next(iter(cards))
    item = evidence(url)
    print('Sample URL:', url)
    print('Legal body characters:', len(item['text']))
    print('Metadata fields:', len(item['metadata']))
    print('Official revision pairs:', len(item['revision_pairs']))
    print('Pairs read:', len(item['comparisons']))
    print('Changed text blocks:', sum(len(x['changes']) for x in item['comparisons']))
    print('All listed revision pairs processed:', item['comparison_complete'])
    for section in (11,15,16):
        try:
            print('Official weekly PDF records, section', section, ':', len(weekly_files(section)))
        except Exception as exc:
            print('Weekly listing check failed, section', section, ':', type(exc).__name__)
    print('Coverage: recent-card sample plus weekly PDF inventory; NOT full daily coverage.')
    print('AI calls: 0; Telegram posts: 0; collection flag unchanged.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ARLIS check failed:', type(exc).__name__)
        raise SystemExit(1)
