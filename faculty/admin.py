import secrets

from django.contrib import admin
from django.contrib.auth.models import User

from .models import Faculty, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department", "course", "year", "semester", "subject_type", "credits", "faculty")
    list_filter = ("department", "course", "year", "semester", "subject_type")
    search_fields = ("name", "code")



# ============================================================
# FACULTY ADMIN
# Auto-creates a login account when a Faculty member is added
# without one, so every faculty member can sign in immediately.
# ============================================================

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "faculty_id",
        "email",
        "department",
        "is_approved",
        "user",
        "designation",
        "is_active",
    )

    search_fields = (
        "name",
        "faculty_id",
        "email",
    )

    def save_model(self, request, obj, form, change):

        if obj.user_id is None:

            # Reuse an existing login if one already exists with
            # this email, instead of creating a duplicate account.
            user = User.objects.filter(email=obj.email).first()

            if user is None:

                username = obj.faculty_id.strip().lower()
                password = secrets.token_urlsafe(6)

                user = User.objects.create(
                    username=username,
                    email=obj.email,
                )
                user.set_password(password)
                user.save()

                self.message_user(
                    request,
                    f"Login created for {obj.name}: "
                    f"username '{username}', password '{password}'. "
                    f"Share this with the faculty member — it will not be shown again."
                )
            else:
                self.message_user(
                    request,
                    f"Linked {obj.name} to their existing login "
                    f"'{user.username}'."
                )

            obj.user = user

        super().save_model(request, obj, form, change)
