"""Downloads and extracts ONE official PDF. No AI, Telegram or database writes."""
from arlis_source import weekly_files
from pdf_sources import download, extract_pdf


def main():
    try:
        import pypdf
    except ImportError:
        print('PDF dependency missing. Install requirements.txt using cPanel pip install.')
        return
    print('pypdf available:', pypdf.__version__, flush=True)
    records = weekly_files(11)
    if not records:
        print('No official law PDFs available in the current listing.')
        return
    url = next(iter(records))
    print('Sample source:', url, flush=True)
    item = extract_pdf(download(url))
    print('PDF pages:',item['pages'])
    print('Extracted characters:',len(item['text']))
    print('Armenian characters:',item['armenian_characters'])
    print('Extraction status:',item['status'])
    print('Pages requiring manual review:',item['uncertain_pages'])
    print('Embedded official links:',len(item['official_links']))
    print('AI requests: 0; Telegram posts: 0; database writes: 0.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('PDF test failed:',type(exc).__name__)
        raise SystemExit(1)
