from datetime import datetime


def format_date(value, format='%d.%m.%Y %H:%M'):
    """Фильтр для форматирования даты."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(format)
