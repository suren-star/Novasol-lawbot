"""One small AI test and read-only source check; no Telegram messages or collection."""
import json
import os
import re
from urllib.parse import urljoin, urlsplit
from hosting import configuration
from bot import request, parse_page, APIError

def main():
    configuration()
    key = os.getenv('OPENAI_API_KEY', '')
    model = os.getenv('OPENAI_MODEL', '')
    if not key or not model:
        print('OpenAI: missing settings')
    else:
        try:
            result = json.loads(request('https://api.openai.com/v1/chat/completions', {
                'model':model, 'max_tokens':80,
                'response_format':{'type':'json_object'},
                'messages':[{'role':'system','content':'Return a JSON object with ok set to true.'},
                            {'role':'user','content':'Connection test. Return JSON only.'}]
            }, {'Authorization':'Bearer ' + key, 'Content-Type':'application/json'}))
            value = json.loads(result['choices'][0]['message']['content'])
            print('OpenAI generation test:', 'OK' if value.get('ok') is True else 'UNEXPECTED RESPONSE')
        except APIError as exc:
            # APIError contains only a controlled status or network label.
            print('OpenAI generation test:', str(exc))
            print('401: key rejected; 403: access denied; 404: model unavailable; 429: quota or rate limit.')
        except Exception as exc:
            print('OpenAI generation test:', type(exc).__name__)
    try:
        url = 'https://www.arlis.am/hy/'
        html = request(url)
        page = parse_page(html)
        links = set()
        for href, title in page.links:
            full = urljoin(url, href)
            parsed = urlsplit(full)
            if parsed.hostname in ('arlis.am','www.arlis.am') and re.fullmatch(r'/hy/acts/\d+/?', parsed.path):
                links.add(full)
        print('ARLIS homepage fetch: OK')
        print('ARLIS readable act links:', len(links))
        print('ARLIS Armenian publication heading:', 'Վերջին հրապարակումները' in html)
        print('Coverage: homepage sample only, complete monitoring NOT validated.')
    except APIError as exc:
        print('ARLIS source check:', str(exc))
    except Exception as exc:
        print('ARLIS source check:', type(exc).__name__)
    print('No Telegram messages sent. Collection flag unchanged.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Setup error:', type(exc).__name__)
