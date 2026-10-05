from django.db import models


class AnalyticsSetting(models.Model):
    """
    Configurable parameters for college academic analytics and student risk scoring.
    Singleton-pattern configuration.
    """
    attendance_warning_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=75.00,
        help_text="Attendance percentage below which warning is flagged (Safe: >= this value)."
    )
    attendance_critical_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=65.00,
        help_text="Attendance percentage below which critical shortage is flagged (Critical: < this value)."
    )
    marks_passing_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40.00,
        help_text="Marks percentage required to pass a subject."
    )
    marks_distinction_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=75.00,
        help_text="Marks percentage considered high-performing / distinction."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Analytics Setting"
        verbose_name_plural = "Analytics Settings"

    def __str__(self):
        return f"Analytics Settings (Safe >= {self.attendance_warning_threshold}%, Critical < {self.attendance_critical_threshold}%)"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
