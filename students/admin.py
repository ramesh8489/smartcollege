import secrets

from django.contrib import admin
from django.contrib.auth.models import User

from .models import Department, Course, Student


admin.site.register(Department)


@admin.action(description="Promote selected students to next year")
def promote_students(modeladmin, request, queryset):
    updated = 0
    for student in queryset.filter(is_active=True):
        student.year += 1
        student.save(update_fields=["year"])
        updated += 1
    modeladmin.message_user(request, f"Promoted {updated} student(s) to the next year.")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "department")
    list_filter = ("department",)
    search_fields = ("name",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "name", "roll_no", "sif_number", "department", "course", "year",
        "is_approved", "user", "is_active",
    )
    actions = [promote_students]
    search_fields = ("name", "roll_no", "sif_number", "email")

    def save_model(self, request, obj, form, change):
        if obj.user_id is None:
            user = User.objects.filter(email=obj.email).first()
            if user is None:
                username = obj.roll_no.strip().lower()
                password = secrets.token_urlsafe(6)
                user = User.objects.create(username=username, email=obj.email)
                user.set_password(password)
                user.save()
                self.message_user(
                    request,
                    f"Login created for {obj.name}: username '{username}', "
                    f"password '{password}'. Share this with the student — it will not be shown again.",
                )
            else:
                self.message_user(
                    request,
                    f"Linked {obj.name} to their existing login '{user.username}'.",
                )
            obj.user = user
        super().save_model(request, obj, form, change)
