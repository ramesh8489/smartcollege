from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from .seo_views import landing_home, robots_txt, sitemap_xml


urlpatterns = [
    path("", landing_home, name="home"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),

    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("students/", include("students.urls")),
    path("faculty/", include("faculty.urls")),
    path("reports/", include("reports.urls")),
    path("timetable/", include("timetable.urls")),
    path("fees/", include("fees.urls")),
    path("library/", include("library.urls")),
    path("exams/", include("exams.urls")),
    path("assignments/", include("assignments.urls")),
    path("leaves/", include("student_leave.urls")),
    path("placements/", include("placements.urls")),
    path("certificates/", include("certificates.urls")),
    path("documents/", include("certificates.document_urls")),
    path("analytics/", include("analytics.urls")),
    path("hostel/", include("hostel.urls")),
    path("transport/", include("transport.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
