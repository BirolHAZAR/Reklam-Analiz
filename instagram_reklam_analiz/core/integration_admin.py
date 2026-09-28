from django import forms
from django.contrib import admin

from core.models import IntegrationApplication


class IntegrationApplicationForm(forms.ModelForm):
    class Meta:
        model = IntegrationApplication
        fields = "__all__"
        widgets = {
            "client_secret": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
            "developer_token": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("client_secret", "developer_token"):
            self.fields[name].required = False
            self.fields[name].help_text = "Şifreli saklanır. Kayıtlı değeri korumak için boş bırakın."

    def clean(self):
        data = super().clean()
        for name in ("client_secret", "developer_token"):
            if not data.get(name) and self.instance.pk:
                data[name] = getattr(self.instance, name)
        return data


@admin.register(IntegrationApplication)
class IntegrationApplicationAdmin(admin.ModelAdmin):
    form = IntegrationApplicationForm
    list_display = ("provider", "enabled", "redirect_uri", "updated_at")
    readonly_fields = ("updated_at",)

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)
