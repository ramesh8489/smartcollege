from django.test import TestCase
from django.contrib.auth.models import User
from students.models import Department, Course, Student


class StudentSIFNumberTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="School of Computing")
        self.course = Course.objects.create(name="B.Tech Computer Science", department=self.dept)

    def test_sif_number_auto_generated_when_blank(self):
        """When student is created without sif_number, a 7-digit unique SIF is auto-generated."""
        user = User.objects.create_user(username="testuser1", password="password123")
        student = Student.objects.create(
            user=user,
            name="Test Student 1",
            roll_no="CS0091",
            email="test1@college.edu",
            department=self.dept,
            course=self.course,
            year=1,
        )
        self.assertIsNotNone(student.sif_number)
        self.assertEqual(len(student.sif_number), 7)
        self.assertTrue(student.sif_number.isdigit())

    def test_custom_sif_number_retained_if_provided(self):
        """When an explicit sif_number is provided, it is preserved."""
        user = User.objects.create_user(username="testuser2", password="password123")
        student = Student.objects.create(
            user=user,
            name="Test Student 2",
            roll_no="CS0092",
            sif_number="CUSTOM123",
            email="test2@college.edu",
            department=self.dept,
            course=self.course,
            year=1,
        )
        self.assertEqual(student.sif_number, "CUSTOM123")

    def test_sif_number_auto_generated_on_save_if_cleared(self):
        """If sif_number is cleared or empty on save, an auto-generated SIF number is set."""
        user = User.objects.create_user(username="testuser3", password="password123")
        student = Student.objects.create(
            user=user,
            name="Test Student 3",
            roll_no="CS0093",
            sif_number="TEMP999",
            email="test3@college.edu",
            department=self.dept,
            course=self.course,
            year=1,
        )
        self.assertEqual(student.sif_number, "TEMP999")
        student.sif_number = ""
        student.save()
        student.refresh_from_db()
        self.assertIsNotNone(student.sif_number)
        self.assertEqual(len(student.sif_number), 7)
        self.assertTrue(student.sif_number.isdigit())

    def test_registration_view_auto_generates_sif(self):
        """Registration view automatically generates SIF without student inputting it."""
        response = self.client.post("/accounts/register/", {
            "role": "student",
            "name": "Auto SIF Student",
            "email": "autosif@college.edu",
            "username": "autosifuser",
            "password": "Password123",
            "confirm_password": "Password123",
            "department": self.dept.id,
            "course": self.course.id,
            "roll_no": "CS0099",
            "year": 1,
        })
        self.assertEqual(response.status_code, 200)
        student = Student.objects.get(roll_no="CS0099")
        self.assertIsNotNone(student.sif_number)
        self.assertEqual(len(student.sif_number), 7)
        self.assertIn(student.sif_number, response.content.decode("utf-8"))
