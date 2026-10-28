from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import RedirectView
from .seo_views import landing_home, robots_txt, sitemap_xml
from .pwa_views import manifest_json, service_worker_js, offline_view, app_download_view, download_app_shortcut


urlpatterns = [
    path("", landing_home, name="home"),
    path("favicon.ico", RedirectView.as_view(url="/static/images/pwa/favicon.png", permanent=True)),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),

    # PWA (Progressive Web Application) & Mobile App Installation
    path("manifest.webmanifest", manifest_json, name="pwa_manifest"),
    path("manifest.json", manifest_json, name="pwa_manifest_json"),
    path("sw.js", service_worker_js, name="service_worker_js"),
    path("offline/", offline_view, name="offline_view"),
    path("app/download/", app_download_view, name="app_download"),
    path("app/download-launcher/", download_app_shortcut, name="download_app_shortcut"),

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
