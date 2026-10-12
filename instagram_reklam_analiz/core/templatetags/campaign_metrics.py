from django import template
from core.templatetags.tr_numbers import tr_decimal

register = template.Library()


@register.filter
def report_number(value, decimals=0):
    return "—" if value is None or value == "" else tr_decimal(value, decimals)


@register.filter
def report_percent(value):
    return "—" if value is None or value == "" else "%" + tr_decimal(value, 2)
