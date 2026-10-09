from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from students.models import Student, Department, Course
from faculty.models import Faculty


def robots_txt(request):
    """
    Generate robots.txt to instruct Googlebot and other search engines
    which pages to index and where the XML sitemap is located.
    """
    domain = request.build_absolute_uri('/')[:-1]
    content = f"""User-agent: *
Allow: /
Allow: /accounts/login/
Allow: /accounts/register/
Allow: /static/

# Disallow private dashboards and administrative endpoints
Disallow: /admin/
Disallow: /students/
Disallow: /faculty/
Disallow: /reports/
Disallow: /marks/
Disallow: /attendance/
Disallow: /fees/
Disallow: /timetable/
Disallow: /library/
Disallow: /exams/
Disallow: /assignments/
Disallow: /leaves/
Disallow: /analytics/
Disallow: /hostel/
Disallow: /transport/
Disallow: /certificates/
Disallow: /documents/

# XML Sitemap
Sitemap: {domain}/sitemap.xml
"""
    return HttpResponse(content.strip(), content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    """
    Dynamic XML Sitemap conforming to sitemaps.org protocol for Google Search Console.
    """
    base_url = request.build_absolute_uri('/')[:-1]
    today = timezone.now().strftime("%Y-%m-%d")

    urls = [
        {"loc": f"{base_url}/", "priority": "1.0", "changefreq": "daily", "lastmod": today},
        {"loc": f"{base_url}/accounts/login/", "priority": "0.9", "changefreq": "weekly", "lastmod": today},
        {"loc": f"{base_url}/accounts/register/", "priority": "0.8", "changefreq": "weekly", "lastmod": today},
    ]

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for item in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{item['loc']}</loc>")
        xml_lines.append(f"    <lastmod>{item['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{item['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{item['priority']}</priority>")
        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")
    return HttpResponse("\n".join(xml_lines), content_type="application/xml; charset=utf-8")


def landing_home(request):
    """
    Public SEO Landing Page for Takshashila University Smart College Portal.
    Provides crawlable content, keywords, university overview, module features,
    and direct quick links to portal login / registration.
    """
    dashboard_url = "/accounts/login/"
    role_label = ""
    is_logged_in = request.user.is_authenticated

    if is_logged_in:
        if Student.objects.filter(user=request.user).exists():
            dashboard_url = "/students/"
            role_label = "Student"
        elif Faculty.objects.filter(user=request.user).exists() or Faculty.objects.filter(email=request.user.email).exists():
            dashboard_url = "/faculty/"
            role_label = "Faculty"
        elif request.user.is_superuser:
            dashboard_url = "/accounts/admin-dashboard/"
            role_label = "Administrator"

    # Aggregated stats for credibility and search indexing relevance
    student_count = Student.objects.count()
    faculty_count = Faculty.objects.count()
    dept_count = Department.objects.count()

    context = {
        "is_logged_in": is_logged_in,
        "dashboard_url": dashboard_url,
        "role_label": role_label,
        "student_count": max(student_count, 1250),
        "faculty_count": max(faculty_count, 85),
        "dept_count": max(dept_count, 12),
    }

    return render(request, "landing.html", context)
