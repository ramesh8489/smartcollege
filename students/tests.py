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
        self.assertIn(student.sif_number, response.content.decode("utf-8"))


class PWAMobileAppTestCase(TestCase):
    def test_manifest_webmanifest_endpoint(self):
        """Verify /manifest.webmanifest returns valid JSON with PWA configuration."""
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        data = response.json()
        self.assertEqual(data["name"], "Takshashila University · Smart College")
        self.assertEqual(data["short_name"], "Takshashila")
        self.assertEqual(data["display"], "standalone")
        self.assertTrue(len(data["icons"]) >= 2)

    def test_manifest_json_alias(self):
        """Verify /manifest.json returns the same valid PWA manifest."""
        response = self.client.get("/manifest.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        data = response.json()
        self.assertEqual(data["short_name"], "Takshashila")

    def test_service_worker_endpoint(self):
        """Verify /sw.js is served from root scope with correct headers."""
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertEqual(response.get("Service-Worker-Allowed"), "/")
        self.assertIn("takshashila-pwa-v1", response.content.decode("utf-8"))

    def test_offline_page_endpoint(self):
        """Verify /offline/ renders the offline fallback view."""
        response = self.client.get("/offline/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You're Currently Offline", status_code=200)

    def test_app_download_showcase_page(self):
        """Verify /app/download/ renders the dedicated mobile app page with installation steps."""
        response = self.client.get("/app/download/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Takshashila University Mobile App")
        self.assertContains(response, "Install Mobile App (PWA)")
        self.assertContains(response, "Android")
        self.assertContains(response, "iPhone")


class StudentDashboardPWATestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="School of Engineering")
        self.course = Course.objects.create(name="B.Tech AI & Data Science", department=self.dept)
        self.user = User.objects.create_user(username="teststudent_dash", password="password123")
        self.student = Student.objects.create(
            user=self.user,
            name="John Doe",
            roll_no="AI2026",
            sif_number="SIF1234",
            email="johndoe@college.edu",
            department=self.dept,
            course=self.course,
            year=1,
            is_approved=True,
        )

    def test_student_dashboard_pwa_install_elements(self):
        """Student dashboard should feature the PWA Mobile App Install button and triggers."""
        self.client.force_login(self.user)
        response = self.client.get("/students/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # PWA Mobile App Install elements
        self.assertIn("Install Mobile App", content)
        self.assertIn("triggerPWAInstall()", content)
        self.assertIn("manifest.webmanifest", content)

        # Core Academic sections remain clean and intact
        self.assertIn("Subject-wise attendance", content)
        self.assertIn("Marks summary", content)
        self.assertIn("Exam Results", content)


