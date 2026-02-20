from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
