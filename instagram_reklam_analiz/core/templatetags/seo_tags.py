from django import template
from core.seo import metadata

register = template.Library()


@register.inclusion_tag("includes/seo.html", takes_context=True)
def seo_meta(context):
    return metadata(context)
