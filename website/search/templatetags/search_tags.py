from django import template

register = template.Library()


@register.filter(name='get')
def my_get(d, k):
    return d.get(k, None)