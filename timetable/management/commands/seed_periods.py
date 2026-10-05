import datetime

from django.core.management.base import BaseCommand

from timetable.models import Period


# 8 one-hour periods, 9 AM to 5 PM, with a lunch break built into
# the gap between period 4 and period 5. Edit in /admin/ if your
# college's actual hours differ.
DEFAULT_PERIODS = [
    (1, "09:00", "10:00"),
    (2, "10:00", "11:00"),
    (3, "11:00", "12:00"),
    (4, "12:00", "13:00"),
    (5, "14:00", "15:00"),
    (6, "15:00", "16:00"),
    (7, "16:00", "17:00"),
    (8, "17:00", "18:00"),
]


class Command(BaseCommand):

    help = (
        "Seeds the 8 standard college hour/periods (9 AM - 6 PM "
        "with a lunch gap). Safe to run more than once."
    )

    def handle(self, *args, **options):

        created_count = 0

        for number, start, end in DEFAULT_PERIODS:

            period, created = Period.objects.get_or_create(
                period_number=number,
                defaults={
                    "start_time": datetime.datetime.strptime(start, "%H:%M").time(),
                    "end_time": datetime.datetime.strptime(end, "%H:%M").time(),
                }
            )

            if created:
                created_count += 1

        self.stdout.write(
            f"Done. {created_count} new period(s) added "
            f"({Period.objects.count()} total)."
        )
