from django.urls import path
from . import views


urlpatterns = [

    # Student Attendance Excel
    path(
        "student/attendance/excel/",
        views.student_attendance_excel,
        name="student_attendance_excel"
    ),

    # Student Marks Excel
    path(
        "student/marks/excel/",
        views.student_marks_excel,
        name="student_marks_excel"
    ),

    # Faculty Attendance Excel
    path(
        "faculty/attendance/excel/",
        views.faculty_attendance_excel,
        name="faculty_attendance_excel"
    ),

    # Faculty Marks Excel
    path(
        "faculty/marks/excel/",
        views.faculty_marks_excel,
        name="faculty_marks_excel"
    ),


    path(
        "student/attendance/pdf/",
        views.student_attendance_pdf,
        name="student_attendance_pdf"
    ),

    # Student Marks PDF
    path(
        "student/marks/pdf/",
        views.student_marks_pdf,
        name="student_marks_pdf"
    ),

    # Faculty Attendance PDF
    path(
        "faculty/attendance/pdf/",
        views.faculty_attendance_pdf,
        name="faculty_attendance_pdf"
    ),

    # Faculty Marks PDF
    path(
        "faculty/marks/pdf/",
        views.faculty_marks_pdf,
        name="faculty_marks_pdf"
    ),

    # Admin: students Excel (filtered)
    path(
        "admin/students/excel/",
        views.admin_students_excel,
        name="admin_students_excel"
    ),

]

