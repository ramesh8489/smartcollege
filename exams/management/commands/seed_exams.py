from django.core.management.base import BaseCommand
import datetime
from decimal import Decimal
from exams.models import Exam, ExamSchedule, StudentExamMark
from students.models import Course, Department, Student
from faculty.models import Subject, Faculty
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Seed sample examinations, schedule slots, and student exam marks."

    def handle(self, *args, **options):
        admin_user = User.objects.filter(is_superuser=True).first()

        c25 = Course.objects.filter(id=25).first()
        c26 = Course.objects.filter(id=26).first()
        c1 = Course.objects.filter(id=1).first()

        fac1 = Faculty.objects.filter(id=1).first() or Faculty.objects.first()
        fac2 = Faculty.objects.filter(id=2).first() or fac1

        dept = c25.department if c25 else Department.objects.first()

        sub1, _ = Subject.objects.get_or_create(
            code='CS101',
            defaults={
                'name': 'Python Programming',
                'department': dept,
                'faculty': fac1,
                'course': c25,
                'year': 2,
                'semester': 3,
                'credits': 4.0,
                'subject_type': 'THEORY',
            }
        )
        sub2, _ = Subject.objects.get_or_create(
            code='CS001',
            defaults={
                'name': 'Deep Learning',
                'department': dept,
                'faculty': fac2,
                'course': c25,
                'year': 2,
                'semester': 3,
                'credits': 4.0,
                'subject_type': 'THEORY',
            }
        )
        sub3, _ = Subject.objects.get_or_create(
            code='CS203',
            defaults={
                'name': 'Cloud Computing & DevOps',
                'department': dept,
                'faculty': fac1,
                'course': c25,
                'year': 2,
                'semester': 3,
                'credits': 3.0,
                'subject_type': 'THEORY',
            }
        )
        sub4, _ = Subject.objects.get_or_create(
            code='CS204P',
            defaults={
                'name': 'AI & Deep Learning Lab',
                'department': dept,
                'faculty': fac2,
                'course': c25,
                'year': 2,
                'semester': 3,
                'credits': 2.0,
                'subject_type': 'PRACTICAL',
            }
        )

        # 1. CAT 1
        e1, _ = Exam.objects.get_or_create(
            name='Continuous Assessment Test 1 (CAT-1) - Oct 2026',
            defaults={
                'exam_type': 'CAT 1',
                'academic_year': '2026-2027',
                'semester': 3,
                'course': c25,
                'year': 2,
                'start_date': datetime.date(2026, 10, 10),
                'end_date': datetime.date(2026, 10, 18),
                'description': 'Continuous Assessment Test 1 covering Units 1 and 2. Attendance is strictly mandatory. Hall tickets must be displayed.',
                'is_active': True,
                'created_by': admin_user,
            }
        )
        s1, _ = ExamSchedule.objects.get_or_create(
            exam=e1, subject=sub1,
            defaults={'exam_date': datetime.date(2026, 10, 12), 'start_time': datetime.time(10, 0), 'end_time': datetime.time(11, 30), 'room_number': 'LH-201', 'room': 'LH-201', 'invigilator': fac1, 'max_marks': 50, 'status': 'Completed'}
        )
        s2, _ = ExamSchedule.objects.get_or_create(
            exam=e1, subject=sub2,
            defaults={'exam_date': datetime.date(2026, 10, 14), 'start_time': datetime.time(10, 0), 'end_time': datetime.time(11, 30), 'room_number': 'LH-201', 'room': 'LH-201', 'invigilator': fac2, 'max_marks': 50, 'status': 'Completed'}
        )
        s3, _ = ExamSchedule.objects.get_or_create(
            exam=e1, subject=sub3,
            defaults={'exam_date': datetime.date(2026, 10, 16), 'start_time': datetime.time(10, 0), 'end_time': datetime.time(11, 30), 'room_number': 'LH-202', 'room': 'LH-202', 'invigilator': fac1, 'max_marks': 50, 'status': 'Ongoing'}
        )

        # 2. CAT 2
        e2, _ = Exam.objects.get_or_create(
            name='Continuous Assessment Test 2 (CAT-2) - Nov 2026',
            defaults={
                'exam_type': 'CAT 2',
                'academic_year': '2026-2027',
                'semester': 3,
                'course': c25,
                'year': 2,
                'start_date': datetime.date(2026, 11, 5),
                'end_date': datetime.date(2026, 11, 12),
                'description': 'Continuous Assessment Test 2 covering Units 3 and 4.',
                'is_active': True,
                'created_by': admin_user,
            }
        )

        # 3. Model Exam
        e3, _ = Exam.objects.get_or_create(
            name='Odd Semester Model Examination 2026',
            defaults={
                'exam_type': 'Model Exam',
                'academic_year': '2026-2027',
                'semester': 3,
                'course': c25,
                'year': 2,
                'start_date': datetime.date(2026, 11, 20),
                'end_date': datetime.date(2026, 11, 28),
                'description': 'Comprehensive model examination adhering to the final University question paper blueprint (100 marks, 3 hours).',
                'is_active': True,
                'created_by': admin_user,
            }
        )

        # 4. Practical Exam
        e4, _ = Exam.objects.get_or_create(
            name='Odd Semester Practical & Viva Examination 2026',
            defaults={
                'exam_type': 'Practical Exam',
                'academic_year': '2026-2027',
                'semester': 3,
                'course': c25,
                'year': 2,
                'start_date': datetime.date(2026, 11, 15),
                'end_date': datetime.date(2026, 11, 18),
                'description': 'Practical laboratory execution, program demonstrations, and external examiner viva-voce.',
                'is_active': True,
                'created_by': admin_user,
            }
        )
        s4, _ = ExamSchedule.objects.get_or_create(
            exam=e4, subject=sub4,
            defaults={'exam_date': datetime.date(2026, 11, 16), 'start_time': datetime.time(9, 30), 'end_time': datetime.time(12, 30), 'room_number': 'Lab-101', 'room': 'Lab-101', 'invigilator': fac2, 'max_marks': 100, 'status': 'Scheduled'}
        )

        # 5. Internal Exam
        e5, _ = Exam.objects.get_or_create(
            name='Internal Assessment Test 1 (IAT-1) - Sept 2026',
            defaults={
                'exam_type': 'Internal Exam',
                'academic_year': '2026-2027',
                'semester': 3,
                'course': c25,
                'year': 2,
                'start_date': datetime.date(2026, 9, 15),
                'end_date': datetime.date(2026, 9, 22),
                'description': 'Internal assessment cycle 1 evaluating foundational modules.',
                'is_active': True,
                'created_by': admin_user,
            }
        )

        # 6. Semester Exam
        e6, _ = Exam.objects.get_or_create(
            name='End Semester University Examination - Dec 2026',
            defaults={
                'exam_type': 'Semester Exam',
                'academic_year': '2026-2027',
                'semester': 3,
                'course': c1 if c1 else c25,
                'year': 2,
                'start_date': datetime.date(2026, 12, 1),
                'end_date': datetime.date(2026, 12, 18),
                'description': 'Centralized End Semester University Examination held under the Controller of Examinations.',
                'is_active': True,
                'created_by': admin_user,
            }
        )

        # 7. CAT 3
        e7, _ = Exam.objects.get_or_create(
            name='Continuous Assessment Test 3 (CAT-3) Improvement Exam',
            defaults={
                'exam_type': 'CAT 3',
                'academic_year': '2026-2027',
                'semester': 3,
                'course': c25,
                'year': 2,
                'start_date': datetime.date(2026, 11, 28),
                'end_date': datetime.date(2026, 12, 3),
                'description': 'Improvement assessment for students desiring to upgrade CAT scores.',
                'is_active': False,
                'created_by': admin_user,
            }
        )

        # Ensure student 1 (ramesh) is enrolled in course 25 for demo testing
        st_ramesh = Student.objects.filter(id=1).first()
        if st_ramesh and not st_ramesh.course:
            st_ramesh.course = c25
            st_ramesh.save(update_fields=["course"])

        # Seed realistic exam marks for students in Course 25
        students_c25 = Student.objects.filter(course=c25, year=2)

        # Sample scores for students
        marks_dataset = [
            (sub1, Decimal("44.50"), "Good programming logic in Section B."),
            (sub2, Decimal("42.00"), "Clear mathematical formulation of backprop."),
            (sub3, Decimal("46.00"), "Excellent DevOps pipeline implementation."),
        ]

        marks_created = 0
        for st in students_c25:
            # Vary marks slightly per student
            multiplier = Decimal("1.0") if st.id == 3 else Decimal("0.9")
            for sub, score, rem in marks_dataset:
                obtained = min(score * multiplier, Decimal("50.00"))
                m_obj, created = StudentExamMark.objects.get_or_create(
                    student=st,
                    exam=e1,
                    subject=sub,
                    defaults={
                        "max_marks": 50,
                        "marks_obtained": obtained,
                        "remarks": rem,
                        "entered_by": admin_user,
                    }
                )
                if not created:
                    m_obj.marks_obtained = obtained
                    m_obj.max_marks = 50
                    m_obj.remarks = rem
                    m_obj.save()
                marks_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded! Total Exams: {Exam.objects.count()}, Schedules: {ExamSchedule.objects.count()}, Marks: {StudentExamMark.objects.count()}"
        ))
