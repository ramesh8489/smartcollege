import secrets

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from students.models import Student
from faculty.models import Faculty


class Command(BaseCommand):
    """
    One-time fix-up command.

    Finds any Student or Faculty record that has no linked
    login account (e.g. created directly in /admin/ before
    the auto-create logic existed) and creates one. If a User
    with the same email already exists (an older record that
    was matched by email instead of a direct link), that
    existing account is reused instead of creating a duplicate.

    Usage:
        python manage.py create_missing_logins
    """

    help = (
        "Creates login accounts for any Student/Faculty "
        "record that doesn't already have one."
    )

    def link_or_create(self, email, username_hint):

        user = User.objects.filter(email=email).first()

        if user is not None:
            return user, None

        username = username_hint.strip().lower()
        password = secrets.token_urlsafe(6)

        user = User.objects.create(
            username=username,
            email=email,
        )

        user.set_password(password)
        user.save()

        return user, password

    def handle(self, *args, **options):

        created_any = False

        for student in Student.objects.filter(user__isnull=True):

            user, password = self.link_or_create(
                student.email,
                student.roll_no
            )

            student.user = user
            student.save()

            created_any = True

            if password:
                self.stdout.write(
                    f"Student '{student.name}': "
                    f"username='{user.username}', password='{password}'"
                )
            else:
                self.stdout.write(
                    f"Student '{student.name}': "
                    f"linked to existing login '{user.username}'"
                )

        for faculty in Faculty.objects.filter(user__isnull=True):

            user, password = self.link_or_create(
                faculty.email,
                faculty.faculty_id
            )

            faculty.user = user
            faculty.save()

            created_any = True

            if password:
                self.stdout.write(
                    f"Faculty '{faculty.name}': "
                    f"username='{user.username}', password='{password}'"
                )
            else:
                self.stdout.write(
                    f"Faculty '{faculty.name}': "
                    f"linked to existing login '{user.username}'"
                )

        if not created_any:
            self.stdout.write("Everyone already has a login account.")
