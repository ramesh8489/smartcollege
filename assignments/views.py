import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, FileResponse, Http404
from django.utils import timezone
from django.db.models import Q, Count
from decimal import Decimal

from .models import Assignment, AssignmentSubmission
from .forms import AssignmentForm, AssignmentSubmissionForm, SubmissionEvaluationForm
from students.models import Student, Course
from faculty.models import Faculty, Subject
from timetable.models import Notification, Timetable


def _get_faculty_user(user):
    if not user or not user.is_authenticated:
        return None
    # If the user has a Student profile, they are a student, NEVER faculty!
    if Student.objects.filter(user=user).exists():
        return None
    faculty = Faculty.objects.filter(user=user).first()
    if faculty:
        return faculty
    if user.email:
        return Faculty.objects.filter(email=user.email).first()
    return None


def _get_faculty_assigned_subjects(faculty):
    if not faculty:
        return Subject.objects.none()
    tt_subs = Timetable.objects.filter(faculty=faculty).values_list("subject_id", flat=True)
    return Subject.objects.filter(Q(faculty=faculty) | Q(id__in=tt_subs)).distinct()


# ============================================================
# ASSIGNMENTS LIST / DASHBOARD
# ============================================================

@login_required(login_url="/accounts/login/")
def assignment_list(request):
    """
    Role-aware assignments dashboard:
    - Admin: View and manage all assignments across the institution.
    - Faculty: View and manage assignments for their assigned subjects.
    - Student: View assignments relevant to their degree, year, and semester,
               along with their individual submission status.
    """
    user = request.user
    student = Student.objects.filter(user=user).select_related("course", "department").first()
    is_student = student is not None
    faculty = _get_faculty_user(user) if not is_student else None
    is_admin = (user.is_superuser or user.is_staff) and not is_student
    is_faculty = (faculty is not None) and not is_student

    now = timezone.now()

    # Base QuerySet
    queryset = Assignment.objects.select_related("faculty", "subject", "course", "course__department")

    if is_student:
        # Student view: only active assignments for student's course, year
        queryset = queryset.filter(
            course=student.course,
            year=student.year,
            is_active=True
        )
    elif is_faculty and not is_admin:
        assigned_subjects = _get_faculty_assigned_subjects(faculty)
        queryset = queryset.filter(
            Q(faculty=faculty) | Q(subject__in=assigned_subjects)
        ).distinct()

    # Search & Filters
    q = request.GET.get("q", "").strip()
    assignment_type = request.GET.get("type", "").strip()
    course_id = request.GET.get("course", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    status_filter = request.GET.get("status", "").strip()

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(subject__name__icontains=q) |
            Q(subject__code__icontains=q)
        )

    if assignment_type:
        queryset = queryset.filter(assignment_type=assignment_type)

    if course_id:
        queryset = queryset.filter(course_id=course_id)

    if subject_id:
        queryset = queryset.filter(subject_id=subject_id)

    if status_filter == "active":
        queryset = queryset.filter(is_active=True, submission_deadline__gte=now)
    elif status_filter == "passed":
        queryset = queryset.filter(submission_deadline__lt=now)

    assignments = list(queryset)

    # For student, annotate each assignment with their submission status
    student_submissions_map = {}
    if student:
        subs = AssignmentSubmission.objects.filter(student=student, assignment__in=assignments)
        student_submissions_map = {s.assignment_id: s for s in subs}
        for a in assignments:
            a.user_submission = student_submissions_map.get(a.id)

    # KPI Statistics
    if is_student:
        total_count = len(assignments)
        submitted_count = sum(1 for a in assignments if getattr(a, "user_submission", None))
        pending_count = total_count - submitted_count
        evaluated_count = sum(1 for a in assignments if getattr(a, "user_submission", None) and a.user_submission.status == "Evaluated")
    else:
        all_faculty_assignments = queryset
        total_count = all_faculty_assignments.count()
        total_submissions = AssignmentSubmission.objects.filter(assignment__in=all_faculty_assignments).count()
        pending_evaluation = AssignmentSubmission.objects.filter(assignment__in=all_faculty_assignments, status__in=["Submitted", "Late"]).count()
        evaluated_count = AssignmentSubmission.objects.filter(assignment__in=all_faculty_assignments, status="Evaluated").count()

    courses = Course.objects.all()
    subjects = Subject.objects.all() if is_admin else (_get_faculty_assigned_subjects(faculty) if faculty else Subject.objects.none())
    assignment_types = [t[0] for t in Assignment.ASSIGNMENT_TYPE_CHOICES]

    context = {
        "assignments": assignments,
        "is_student": is_student,
        "is_admin": is_admin,
        "is_faculty": is_faculty,
        "faculty": faculty,
        "student": student,
        "courses": courses,
        "subjects": subjects,
        "assignment_types": assignment_types,
        "total_count": total_count,
        "submitted_count": submitted_count if is_student else total_submissions,
        "pending_count": pending_count if is_student else pending_evaluation,
        "evaluated_count": evaluated_count,
        "now": now,
        "filters": {
            "q": q,
            "type": assignment_type,
            "course": course_id,
            "subject": subject_id,
            "status": status_filter,
        }
    }
    return render(request, "assignments/assignment_list.html", context)


# ============================================================
# ASSIGNMENT DETAIL & SUBMISSIONS
# ============================================================

@login_required(login_url="/accounts/login/")
def assignment_detail(request, pk):
    assignment = get_object_or_404(
        Assignment.objects.select_related("faculty", "subject", "course", "course__department"),
        pk=pk
    )
    user = request.user
    student = Student.objects.filter(user=user).select_related("course", "department").first()
    is_student = student is not None
    faculty = _get_faculty_user(user) if not is_student else None
    is_admin = (user.is_superuser or user.is_staff) and not is_student
    is_faculty = (faculty is not None) and not is_student

    # Check permission for faculty: assigned subjects only
    if is_faculty and not is_admin:
        assigned_subs = _get_faculty_assigned_subjects(faculty)
        if assignment.faculty != faculty and not assigned_subs.filter(id=assignment.subject_id).exists():
            messages.error(request, "You do not have authorization to view this assignment.")
            return redirect("assignment_list")

    # If student, verify course/year cohort
    if is_student:
        if assignment.course != student.course or assignment.year != student.year:
            messages.error(request, "This assignment is not assigned to your course/year cohort.")
            return redirect("assignment_list")

    now = timezone.now()
    submission = None
    submission_form = None

    # Student submission handling
    if is_student:
        submission = AssignmentSubmission.objects.filter(assignment=assignment, student=student).first()

        if request.method == "POST":
            # Check deadline validation
            if assignment.is_deadline_passed and not submission:
                messages.error(request, "The submission deadline for this assignment has passed. Submissions are closed.")
                return redirect("assignment_detail", pk=assignment.pk)

            submission_form = AssignmentSubmissionForm(request.POST, request.FILES, instance=submission)
            if submission_form.is_valid():
                sub = submission_form.save(commit=False)
                sub.assignment = assignment
                sub.student = student
                sub.save()
                messages.success(request, "Your assignment submission has been successfully uploaded!")
                return redirect("assignment_detail", pk=assignment.pk)
        else:
            submission_form = AssignmentSubmissionForm(instance=submission)

    # Faculty / Admin view: roster of enrolled students and their submissions
    submissions_list = []
    enrolled_students = []

    if not is_student and (is_admin or is_faculty):
        enrolled_students = Student.objects.filter(
            course=assignment.course,
            year=assignment.year,
            is_approved=True
        ).order_by("roll_no")

        submissions_dict = {
            s.student_id: s
            for s in assignment.submissions.select_related("student", "evaluated_by")
        }

        for st in enrolled_students:
            sub = submissions_dict.get(st.id)
            submissions_list.append({
                "student": st,
                "submission": sub,
                "status": sub.status if sub else "Not Submitted",
                "submitted_at": sub.submitted_at if sub else None,
                "marks_obtained": sub.marks_obtained if sub else None,
                "percentage": sub.percentage if sub else None,
                "feedback": sub.feedback if sub else "",
            })

    context = {
        "assignment": assignment,
        "student": student,
        "is_student": is_student,
        "faculty": faculty,
        "is_admin": is_admin,
        "is_faculty": is_faculty,
        "now": now,
        "submission": submission,
        "submission_form": submission_form,
        "submissions_list": submissions_list,
        "enrolled_count": len(enrolled_students),
        "submitted_count": assignment.submission_count,
        "evaluated_count": assignment.evaluated_count,
    }
    return render(request, "assignments/assignment_detail.html", context)


# ============================================================
# CREATE / EDIT / DELETE ASSIGNMENT
# ============================================================

@login_required(login_url="/accounts/login/")
def assignment_create(request):
    user = request.user
    if Student.objects.filter(user=user).exists():
        messages.error(request, "Students are not permitted to create assignments.")
        return redirect("assignment_list")

    is_admin = user.is_superuser or user.is_staff
    faculty = _get_faculty_user(user)

    if not (is_admin or faculty):
        messages.error(request, "Only faculty and administrators can create assignments.")
        return redirect("assignment_list")

    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES, faculty=faculty if not is_admin else None)
        if form.is_valid():
            assignment = form.save(commit=False)
            if not is_admin:
                assignment.faculty = faculty
            elif not assignment.faculty_id:
                assignment.faculty = faculty or Faculty.objects.first()

            assignment.save()

            # Dispatch in-app notifications to all students of this cohort
            students = Student.objects.filter(
                course=assignment.course,
                year=assignment.year,
                user__isnull=False
            )
            notifications = [
                Notification(
                    recipient=st.user,
                    title=f"New Assignment: {assignment.title}",
                    message=f"Faculty {assignment.faculty.name} posted a new {assignment.assignment_type} for {assignment.subject.name}. Deadline: {assignment.submission_deadline.strftime('%d %b %Y %H:%M')}.",
                    link=f"/assignments/{assignment.pk}/"
                )
                for st in students
            ]
            if notifications:
                Notification.objects.bulk_create(notifications)

            messages.success(request, f"Assignment '{assignment.title}' created and notifications dispatched!")
            return redirect("assignment_detail", pk=assignment.pk)
    else:
        form = AssignmentForm(faculty=faculty if not is_admin else None)

    return render(request, "assignments/assignment_form.html", {
        "form": form,
        "title": "Create New Assignment",
        "action": "Publish Assignment",
    })


@login_required(login_url="/accounts/login/")
def assignment_edit(request, pk):
    user = request.user
    if Student.objects.filter(user=user).exists():
        messages.error(request, "Students are not permitted to edit assignments.")
        return redirect("assignment_list")

    assignment = get_object_or_404(Assignment, pk=pk)
    is_admin = user.is_superuser or user.is_staff
    faculty = _get_faculty_user(user)

    if not is_admin:
        if not faculty or assignment.faculty != faculty:
            messages.error(request, "You can only edit assignments created by you.")
            return redirect("assignment_list")

    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES, instance=assignment, faculty=faculty if not is_admin else None)
        if form.is_valid():
            form.save()
            messages.success(request, f"Assignment '{assignment.title}' updated successfully!")
            return redirect("assignment_detail", pk=assignment.pk)
    else:
        form = AssignmentForm(instance=assignment, faculty=faculty if not is_admin else None)

    return render(request, "assignments/assignment_form.html", {
        "form": form,
        "assignment": assignment,
        "title": f"Edit: {assignment.title}",
        "action": "Save Changes",
    })


@login_required(login_url="/accounts/login/")
def assignment_delete(request, pk):
    user = request.user
    if Student.objects.filter(user=user).exists():
        messages.error(request, "Students are not permitted to delete assignments.")
        return redirect("assignment_list")

    assignment = get_object_or_404(Assignment, pk=pk)
    is_admin = user.is_superuser or user.is_staff
    faculty = _get_faculty_user(user)

    if not is_admin:
        if not faculty or assignment.faculty != faculty:
            messages.error(request, "You can only delete assignments created by you.")
            return redirect("assignment_list")

    if request.method == "POST":
        title = assignment.title
        assignment.delete()
        messages.success(request, f"Assignment '{title}' deleted successfully.")
        return redirect("assignment_list")

    return render(request, "assignments/assignment_confirm_delete.html", {"assignment": assignment})


# ============================================================
# EVALUATE SUBMISSION
# ============================================================

@login_required(login_url="/accounts/login/")
def evaluate_submission(request, submission_id):
    user = request.user
    if Student.objects.filter(user=user).exists():
        return HttpResponseForbidden("Students cannot evaluate submissions.")

    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related("assignment", "student", "assignment__faculty"),
        pk=submission_id
    )
    assignment = submission.assignment
    is_admin = user.is_superuser or user.is_staff
    faculty = _get_faculty_user(user)

    # Permission check
    if not is_admin:
        if not faculty or assignment.faculty != faculty:
            assigned_subs = _get_faculty_assigned_subjects(faculty)
            if not assigned_subs.filter(id=assignment.subject_id).exists():
                return HttpResponseForbidden("Unauthorized to evaluate this submission.")

    if request.method == "POST":
        form = SubmissionEvaluationForm(request.POST, instance=submission, assignment=assignment)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.evaluated_by = user
            sub.evaluated_at = timezone.now()
            sub.save()

            # Notify student of evaluated marks
            if submission.student.user:
                Notification.objects.create(
                    recipient=submission.student.user,
                    title=f"Assignment Evaluated: {assignment.title}",
                    message=f"Your submission for {assignment.title} was evaluated. Score: {sub.marks_obtained}/{assignment.max_marks} ({sub.percentage}%).",
                    link=f"/assignments/{assignment.pk}/"
                )

            messages.success(request, f"Submission evaluated for {submission.student.name} ({sub.marks_obtained}/{assignment.max_marks}).")
            return redirect("assignment_detail", pk=assignment.pk)
    else:
        form = SubmissionEvaluationForm(instance=submission, assignment=assignment)

    return render(request, "assignments/evaluate_submission.html", {
        "submission": submission,
        "assignment": assignment,
        "form": form,
    })


# ============================================================
# SAFE FILE DOWNLOADS
# ============================================================

@login_required(login_url="/accounts/login/")
def download_material(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if not assignment.attachment:
        raise Http404("No attachment exists for this assignment.")

    # Check permission
    user = request.user
    student = Student.objects.filter(user=user).first()
    faculty = _get_faculty_user(user)
    is_admin = user.is_superuser or user.is_staff

    if student and not (is_admin or faculty):
        if assignment.course != student.course or assignment.year != student.year:
            return HttpResponseForbidden("Unauthorized file download.")

    return FileResponse(assignment.attachment.open("rb"), as_attachment=True, filename=os.path.basename(assignment.attachment.name))


@login_required(login_url="/accounts/login/")
def download_submission(request, submission_id):
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related("assignment", "student", "assignment__faculty"),
        pk=submission_id
    )
    if not submission.submission_file:
        raise Http404("No submission file found.")

    user = request.user
    is_admin = user.is_superuser or user.is_staff
    faculty = _get_faculty_user(user)
    student = Student.objects.filter(user=user).first()

    # Access security check:
    # 1. Student can only download their own submission
    # 2. Faculty can only download for their assigned subject/assignment
    # 3. Admin can download any
    if student and not (is_admin or faculty):
        if submission.student != student:
            return HttpResponseForbidden("You cannot download another student's submission.")
    elif faculty and not is_admin:
        if submission.assignment.faculty != faculty:
            assigned_subs = _get_faculty_assigned_subjects(faculty)
            if not assigned_subs.filter(id=submission.assignment.subject_id).exists():
                return HttpResponseForbidden("Unauthorized to download this submission.")

    return FileResponse(submission.submission_file.open("rb"), as_attachment=True, filename=os.path.basename(submission.submission_file.name))


# ============================================================
# STUDENT MY SUBMISSIONS PORTAL
# ============================================================

@login_required(login_url="/accounts/login/")
def student_submissions_list(request):
    user = request.user
    student = Student.objects.filter(user=user).select_related("course").first()

    if not student:
        messages.error(request, "No student profile found.")
        return redirect("assignment_list")

    submissions = AssignmentSubmission.objects.filter(
        student=student
    ).select_related("assignment", "assignment__subject", "assignment__faculty").order_by("-submitted_at")

    total_submissions = submissions.count()
    evaluated_count = submissions.filter(status="Evaluated").count()

    context = {
        "student": student,
        "submissions": submissions,
        "total_submissions": total_submissions,
        "evaluated_count": evaluated_count,
    }
    return render(request, "assignments/student_submissions_list.html", context)
