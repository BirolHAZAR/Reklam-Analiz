from django import template
from core.templatetags.tr_numbers import tr_int

register = template.Library()


@register.filter
def organic_metric(value):
    return "Veri yok" if value is None else tr_int(value)
