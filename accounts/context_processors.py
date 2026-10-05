from urllib.parse import urlencode

from students.models import Student
from faculty.models import Faculty
from timetable.models import Notification


def _has_faculty(user):
    if not user or not user.is_authenticated:
        return False
    if Student.objects.filter(user=user).exists():
        return False
    return (
        Faculty.objects.filter(user=user).exists()
        or (bool(user.email) and Faculty.objects.filter(email=user.email).exists())
    )


def nav(request):
    """
    Builds the role-aware sidebar for base.html:
    admin, faculty (+ school incharge) or student.
    """

    user = getattr(request, "user", None)

    if user is None or not user.is_authenticated:
        return {}

    path = request.path

    is_student = Student.objects.filter(user=user).exists()
    is_faculty = _has_faculty(user)

    # The section being viewed decides which menu to show;
    # shared pages fall back to the user's own role.
    if path.startswith("/accounts/admin-dashboard") and user.is_superuser:
        role = "admin"
    elif path.startswith("/students") or path.startswith("/reports/student"):
        role = "student"
    elif path.startswith("/faculty") or path.startswith("/reports/faculty"):
        role = "faculty"
    elif is_student:
        role = "student"
    elif user.is_superuser or user.is_staff:
        role = "admin"
    elif is_faculty:
        role = "faculty"
    else:
        role = "student"

    def item(label, url, icon, active=False, badge=None):
        return {
            "label": label, "url": url, "icon": icon,
            "active": active, "badge": badge,
        }

    groups = []
    home = "/accounts/login/"
    unread_notifications = Notification.objects.filter(recipient=user, is_read=False).count()

    if role == "admin":

        from students.models import Student as S
        from faculty.models import Faculty as F

        pending = (
            S.objects.filter(is_approved=False).count()
            + F.objects.filter(is_approved=False).count()
        )

        from timetable.models import FacultyLeaveRequest
        from student_leave.models import StudentLeaveRequest
        from certificates.models import CertificateRequest
        unseen_leaves = FacultyLeaveRequest.objects.filter(
            forwarded_to_admin=True,
            admin_seen=False,
        ).count()
        pending_student_leaves_admin = StudentLeaveRequest.objects.filter(
            status=StudentLeaveRequest.STATUS_INCHARGE_APPROVED
        ).count()
        pending_certs_admin = CertificateRequest.objects.filter(
            status=CertificateRequest.STATUS_PENDING
        ).count()

        home = "/accounts/admin-dashboard/"
        tab = request.GET.get("tab", "overview")
        on_admin = path.startswith("/accounts/admin-dashboard")

        keep = {
            k: request.GET[k]
            for k in ("school", "course", "year")
            if request.GET.get(k)
        }

        def tab_url(name):
            params = dict(keep)
            params["tab"] = name
            return "/accounts/admin-dashboard/?" + urlencode(params)

        groups.append({
            "label": "Administration",
            "items": [
                item("Overview", tab_url("overview"), "home", on_admin and tab == "overview"),
                item("Advanced Analytics", "/analytics/", "chart", path.startswith("/analytics") and "my" not in path and "faculty" not in path),
                item("Students", tab_url("students"), "users", on_admin and tab == "students"),
                item("Faculty", tab_url("faculty"), "award", on_admin and tab == "faculty"),
                item("Approvals", tab_url("approvals"), "inbox", on_admin and tab == "approvals", pending or None),
                item("Student Leaves", tab_url("student_leaves"), "calendar", on_admin and tab == "student_leaves", pending_student_leaves_admin or None),
                item("Leave Messages", tab_url("leave_messages"), "calendar", on_admin and tab == "leave_messages", unseen_leaves or None),
                item("Circulars", tab_url("circulars"), "bell", on_admin and tab == "circulars"),
            ],
        })

        groups.append({
            "label": "Manage",
            "items": [
                item("Django Admin", "/admin/", "shield"),
                item("School Incharges", "/admin/timetable/schoolincharge/", "school"),
                item("Certificates & Docs", "/certificates/admin/", "award", path.startswith("/certificates") or path.startswith("/documents"), pending_certs_admin or None),
                item("Training & Placements", "/placements/", "briefcase", path.startswith("/placements")),
                item("Student Leaves", "/leaves/admin-list/", "calendar", path.startswith("/leaves/admin-list")),
                item("Exam Management", "/exams/", "calendar", path == "/exams/" or path.startswith("/exams/create")),
                item("Exam Marks", "/exams/marks/", "award", path.startswith("/exams/marks")),
                item("Assignments", "/assignments/", "file", path.startswith("/assignments")),
                item("Notifications", "/timetable/notifications/", "bell", path.startswith("/timetable/notifications"), unread_notifications or None),
                item("Fees Management", "/fees/", "file", path.startswith("/fees/")),
                item("Hostel Management", "/hostel/dashboard/", "shield", path.startswith("/hostel")),
                item("Transport Management", "/transport/dashboard/", "bus", path.startswith("/transport")),
            ],
        })

        role_label = "Administrator"
        display = user.get_username()

    elif role == "faculty":

        from timetable.models import SchoolIncharge

        faculty = (
            Faculty.objects.filter(user=user).first()
            or Faculty.objects.filter(email=user.email).first()
        )

        home = "/faculty/"

        items = [
            item("Dashboard", "/faculty/", "home", path == "/faculty/"),
            item("Student Leaves", "/leaves/faculty/", "calendar", path.startswith("/leaves/faculty")),
            item("Assignments", "/assignments/", "file", path.startswith("/assignments")),
            item("Mark Attendance", "/faculty/attendance/", "check", path.startswith("/faculty/attendance/") and "history" not in path),
            item("Attendance History", "/faculty/attendance-history/", "clock", "attendance-history" in path),
            item("Marks Entry", "/faculty/marks/", "edit", path.startswith("/faculty/marks/") and "history" not in path),
            item("Marks History", "/faculty/marks-history/", "chart", "marks-history" in path),
            item("Class Analytics", "/analytics/faculty/", "chart", path.startswith("/analytics/faculty")),
            item("Leave Request", "/faculty/leave-request/", "calendar", path.startswith("/faculty/leave-request")),
        ]

        groups.append({"label": "Teaching", "items": items})

        more = [
            item("My Timetable", "/timetable/my-timetable/", "calendar", path.startswith("/timetable/my-timetable")),
            item("Exam Schedules", "/exams/", "calendar", path == "/exams/"),
            item("Exam Marks", "/exams/marks/", "award", path.startswith("/exams/marks")),
            item("Placement Drives", "/placements/drives/", "briefcase", path.startswith("/placements")),
        ]

        if faculty and SchoolIncharge.objects.filter(faculty=faculty).exists():
            more.append(
                item("School Analytics", "/analytics/", "chart", path == "/analytics/" or (path.startswith("/analytics") and "faculty" not in path and "my" not in path))
            )
            more.append(
                item("Timetable Builder", "/timetable/incharge/", "layers", path == "/timetable/incharge/")
            )
            more.append(
                item("Leave Approvals", "/timetable/incharge-leaves/", "calendar", path.startswith("/timetable/incharge-leaves"))
            )
            more.append(
                item("Student Leaves (School)", "/leaves/incharge/", "calendar", path.startswith("/leaves/incharge"))
            )

        from hostel.models import HostelWarden, Hostel
        if HostelWarden.objects.filter(user=user, is_active=True).exists() or Hostel.objects.filter(warden_incharge=user, is_active=True).exists():
            more.append(item("Hostel Management", "/hostel/dashboard/", "shield", path.startswith("/hostel")))

        from transport.models import TransportStaff
        if TransportStaff.objects.filter(user=user, is_active=True).exists():
            more.append(item("Transport Management", "/transport/dashboard/", "bus", path.startswith("/transport")))

        more.append(item("Circulars", "/timetable/circulars/", "bell", path.startswith("/timetable/circulars")))
        more.append(item("My Profile", "/faculty/profile/", "user", path.startswith("/faculty/profile")))

        groups.append({"label": "Schedule & More", "items": more})

        role_label = "Faculty"
        display = faculty.name if faculty else user.get_username()

    else:

        student = Student.objects.filter(user=user).first()

        home = "/students/"

        groups.append({
            "label": "My Portal",
            "items": [
                item("Dashboard", "/students/", "home", path == "/students/"),
                item("My Analytics", "/analytics/my/", "chart", path.startswith("/analytics/my")),
                item("Certificates & Docs", "/certificates/", "award", path.startswith("/certificates") or path.startswith("/documents")),
                item("Placements & Jobs", "/placements/student/", "briefcase", path.startswith("/placements")),
                item("Leave Requests", "/leaves/", "calendar", path.startswith("/leaves")),
                item("Assignments", "/assignments/", "file", path.startswith("/assignments")),
                item("Exam Schedules", "/exams/", "calendar", path == "/exams/"),
                item("Exam Results", "/exams/my-results/", "award", path.startswith("/exams/my-results")),
                item("Attendance", "/students/attendance-history/", "check", "attendance-history" in path),
                item("Marks", "/students/marks-history/", "chart", "marks-history" in path),
                item("Notifications", "/timetable/notifications/", "bell", path.startswith("/timetable/notifications"), unread_notifications or None),
                item("Circulars", "/timetable/circulars/", "bell", path.startswith("/timetable/circulars")),
                item("Fees & Payments", "/fees/", "file", path.startswith("/fees/")),
                item("Hostel Portal", "/hostel/", "home", path.startswith("/hostel")),
                item("Transport Portal", "/transport/", "bus", path.startswith("/transport")),
                item("My Profile", "/students/profile/", "user", path.startswith("/students/profile")),
            ],
        })

        role_label = "Student"
        display = student.name if student else user.get_username()

    return {
        "nav_groups": groups,
        "nav_home": home,
        "nav_role": role,
        "nav_display": display,
        "nav_initial": (display[:1] or "?").upper(),
        "nav_role_label": role_label,
        "unread_notifications": unread_notifications,
    }
