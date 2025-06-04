def format_authors(authors_dict):
    if not authors_dict:
        return ""
    authors = authors_dict.get('author', [])
    if isinstance(authors, dict):
        return authors.get('text', '')
    return " and ".join(author['text'] for author in authors if 'text' in author)
