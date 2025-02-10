from datetime import datetime


def format_date(value, format='%d.%m.%Y %H:%M'):
    """Фильтр для форматирования даты."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(format)

def truncate(text, length=200, suffix='...'):
    if len(text) <= length:
        return text
    return text[:length].rsplit(' ', 1)[0] + suffix
