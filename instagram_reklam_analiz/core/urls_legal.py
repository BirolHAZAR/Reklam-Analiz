from django.urls import path
from django.views.generic import TemplateView

from core.views.legal import legal_document_detail, legal_document_index


urlpatterns = [
    path("teslimat-ve-aktivasyon/", TemplateView.as_view(template_name="legal/delivery.html"), name="delivery_terms"),
    path("hukuk/", legal_document_index, name="legal_document_index"),
    path("hukuk/<slug:slug>/", legal_document_detail, name="legal_document_detail"),
]
