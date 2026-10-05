from django.contrib import admin
from .models import AnalyticsSetting


@admin.register(AnalyticsSetting)
class AnalyticsSettingAdmin(admin.ModelAdmin):
    list_display = [
        "attendance_warning_threshold",
        "attendance_critical_threshold",
        "marks_passing_threshold",
        "marks_distinction_threshold",
        "updated_at",
    ]

    def has_add_permission(self, request):
        # Singleton pattern: only allow one configuration record
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
