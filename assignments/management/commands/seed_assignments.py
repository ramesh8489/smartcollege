from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from assignments.models import Assignment, AssignmentSubmission
from students.models import Student, Course
from faculty.models import Faculty, Subject
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Seed realistic sample assignments, submissions, and evaluations for SmartCollege"

    def handle(self, *args, **options):
        self.stdout.write("Starting Assignment module seeding...")

        # 1. Fetch existing faculty, course, and subjects
        faculty = Faculty.objects.first()
        if not faculty:
            self.stdout.write(self.style.ERROR("[FAIL] No Faculty found. Please ensure faculty records exist."))
            return

        subject = Subject.objects.filter(faculty=faculty).first() or Subject.objects.first()
        if not subject:
            self.stdout.write(self.style.ERROR("[FAIL] No Subject found. Please ensure subject records exist."))
            return

        course = subject.course or Course.objects.first()
        if not course:
            self.stdout.write(self.style.ERROR("[FAIL] No Course found."))
            return

        # Ensure subject has course
        if not subject.course:
            subject.course = course
            subject.save(update_fields=["course"])

        # Fetch students for this course
        students = Student.objects.filter(course=course, is_approved=True)
        if not students.exists():
            students = Student.objects.filter(course=course)
        if not students.exists():
            students = Student.objects.all()[:3]

        evaluator_user = User.objects.filter(is_superuser=True).first() or (faculty.user if faculty.user else None)

        now = timezone.now()
        yesterday = (now - timedelta(days=2)).date()
        today = now.date()

        # 2. Seed 6 Assignments representing the 6 required types
        sample_assignments_data = [
            {
                "title": "Mini-Project 1: Distributed Microservices Architecture",
                "assignment_type": "Project",
                "description": "Design and implement a scalable microservice architecture with RESTful endpoints, API Gateway, and database replication.",
                "instructions": "1. Submit source repository archive (ZIP) or PDF report.\n2. Include Docker Compose configurations.\n3. Include API documentation with OpenAPI/Swagger specifications.",
                "assigned_date": yesterday,
                "submission_deadline": now + timedelta(days=7),
                "max_marks": 50,
                "year": 2,
                "semester": 4,
                "academic_year": "2026-2027",
            },
            {
                "title": "Lab Record 4: SQL Query Optimization & Indexing",
                "assignment_type": "Lab Record",
                "description": "Perform query execution plan analysis using EXPLAIN ANALYZE on a 500,000 row dataset. Demonstrate B-tree vs Hash indexing speedups.",
                "instructions": "1. Attach execution screenshots.\n2. Submit PDF report formatted with college standard template.\n3. Late submissions will incur a 10% penalty per day.",
                "assigned_date": yesterday,
                "submission_deadline": now + timedelta(days=3),
                "max_marks": 25,
                "year": 2,
                "semester": 4,
                "academic_year": "2026-2027",
            },
            {
                "title": "Homework 3: Dynamic Programming & Greedy Algorithms",
                "assignment_type": "Homework",
                "description": "Solve the 0/1 Knapsack, Longest Common Subsequence, and Activity Selection problem formulations with full proof of optimality.",
                "instructions": "Handwritten or typed PDF submissions accepted. Show step-by-step state recurrence relations.",
                "assigned_date": yesterday,
                "submission_deadline": now + timedelta(days=4),
                "max_marks": 20,
                "year": 2,
                "semester": 4,
                "academic_year": "2026-2027",
            },
            {
                "title": "Seminar Paper: Advances in Generative AI and LLMs",
                "assignment_type": "Seminar",
                "description": "Prepare a 10-page IEEE conference format literature survey on Transformer attention mechanisms and parameter-efficient fine-tuning (PEFT/LoRA).",
                "instructions": "Submit PDF paper with minimum 15 IEEE/ACM peer-reviewed citations. Plagiarism above 15% will result in zero marks.",
                "assigned_date": yesterday,
                "submission_deadline": now + timedelta(days=14),
                "max_marks": 100,
                "year": 2,
                "semester": 4,
                "academic_year": "2026-2027",
            },
            {
                "title": "Case Study: High-Availability Cloud Infrastructure Failover",
                "assignment_type": "Case Study",
                "description": "Critically analyze Netflix's Chaos Engineering and AWS multi-region disaster recovery architecture during major regional outages.",
                "instructions": "Submit analytical case analysis report with architectural diagrams and recovery time objective (RTO) calculations.",
                "assigned_date": yesterday,
                "submission_deadline": now + timedelta(days=10),
                "max_marks": 30,
                "year": 2,
                "semester": 4,
                "academic_year": "2026-2027",
            },
            {
                "title": "Assignment 1: Object-Oriented System Analysis & UML Diagrams",
                "assignment_type": "Assignment",
                "description": "Develop full UML Class, Sequence, and Use-Case diagrams for an Enterprise Hospital Management Information System.",
                "instructions": "Submit PDF documentation exported from StarUML, Lucidchart, or Draw.io with complete domain dictionary.",
                "assigned_date": (now - timedelta(days=10)).date(),
                "submission_deadline": now - timedelta(days=1), # Closed assignment
                "max_marks": 40,
                "year": 2,
                "semester": 4,
                "academic_year": "2026-2027",
            },
        ]

        created_assignments = []
        for data in sample_assignments_data:
            assignment, created = Assignment.objects.get_or_create(
                title=data["title"],
                course=course,
                defaults={
                    "faculty": faculty,
                    "subject": subject,
                    "year": data["year"],
                    "semester": data["semester"],
                    "academic_year": data["academic_year"],
                    "assignment_type": data["assignment_type"],
                    "assigned_date": data["assigned_date"],
                    "submission_deadline": data["submission_deadline"],
                    "max_marks": data["max_marks"],
                    "description": data["description"],
                    "instructions": data["instructions"],
                    "is_active": True,
                }
            )
            # Add sample attachment if not present
            if not assignment.attachment:
                filename = f"guidelines_{assignment.pk}.txt"
                content = f"SmartCollege Academic Assignment Guidelines\nTitle: {assignment.title}\nCourse: {course.name}\nSubject: {subject.name}\nMax Marks: {assignment.max_marks}\n\nPlease follow the department code formatting guidelines.\n"
                assignment.attachment.save(filename, ContentFile(content.encode("utf-8")), save=True)

            created_assignments.append(assignment)
            status_str = "[CREATED]" if created else "[EXISTS]"
            self.stdout.write(f"  {status_str} Assignment: {assignment.title} ({assignment.assignment_type})")

        # 3. Seed Sample Submissions for Students
        if students.exists() and created_assignments:
            student_list = list(students)
            first_student = student_list[0]
            second_student = student_list[1] if len(student_list) > 1 else first_student

            # Submission 1: Evaluated submission on Mini-Project
            proj_assignment = created_assignments[0]
            sub1, s1_created = AssignmentSubmission.objects.get_or_create(
                assignment=proj_assignment,
                student=first_student,
                defaults={
                    "student_remarks": "Completed full microservices architecture with FastAPI and PostgreSQL. Attached Docker Compose and Postman collection.",
                    "status": "Evaluated",
                    "marks_obtained": Decimal("46.50"),
                    "percentage": Decimal("93.00"),
                    "feedback": "Outstanding architectural separation of concerns. Clean API schema and Docker compose health checks verified. Excellent work!",
                    "evaluated_by": evaluator_user,
                    "evaluated_at": now,
                }
            )
            if not sub1.submission_file:
                sub1.submission_file.save(
                    f"solution_{first_student.roll_no}_proj.txt",
                    ContentFile(b"Microservices Implementation Codebase and Architecture Documentation\nStudent: " + first_student.name.encode("utf-8")),
                    save=True
                )
            self.stdout.write(f"  [OK] Submission 1 (Evaluated): {first_student.name} -> {proj_assignment.title} (Score: 46.5/50)")

            # Submission 2: Submitted On-Time on Lab Record
            lab_assignment = created_assignments[1]
            sub2, s2_created = AssignmentSubmission.objects.get_or_create(
                assignment=lab_assignment,
                student=first_student,
                defaults={
                    "student_remarks": "Attached PostgreSQL query execution plans with explain analyze outputs and index benchmarks.",
                    "status": "Submitted",
                }
            )
            if not sub2.submission_file:
                sub2.submission_file.save(
                    f"lab_record_{first_student.roll_no}.pdf",
                    ContentFile(b"%PDF-1.4 SQL Query Optimization Lab Record\nStudent: " + first_student.name.encode("utf-8")),
                    save=True
                )
            self.stdout.write(f"  [OK] Submission 2 (Submitted/Pending): {first_student.name} -> {lab_assignment.title}")

            # Submission 3: Late Submission on closed Assignment 1
            closed_assignment = created_assignments[5]
            if len(student_list) > 1:
                sub3, s3_created = AssignmentSubmission.objects.get_or_create(
                    assignment=closed_assignment,
                    student=second_student,
                    defaults={
                        "student_remarks": "Submitted UML diagrams for Hospital Management System. Apologies for the late upload due to network maintenance.",
                        "status": "Late",
                    }
                )
                if not sub3.submission_file:
                    sub3.submission_file.save(
                        f"uml_diagrams_{second_student.roll_no}.pdf",
                        ContentFile(b"%PDF-1.4 UML Diagrams Hospital System\nStudent: " + second_student.name.encode("utf-8")),
                        save=True
                    )
                self.stdout.write(f"  [OK] Submission 3 (Late): {second_student.name} -> {closed_assignment.title}")

        self.stdout.write(self.style.SUCCESS("[SUCCESS] Assignment module seed completed successfully!"))
