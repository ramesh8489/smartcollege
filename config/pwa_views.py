import os
from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import render


def manifest_json(request):
    """
    Serve the PWA Web App Manifest at root level.
    """
    manifest_path = os.path.join(settings.BASE_DIR, "static", "manifest.webmanifest")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
        response = HttpResponse(content, content_type="application/manifest+json; charset=utf-8")
        response["Access-Control-Allow-Origin"] = "*"
        return response
    except FileNotFoundError:
        raise Http404("Manifest not found")


def service_worker_js(request):
    """
    Serve Service Worker at root scope with required Service-Worker-Allowed header.
    """
    sw_path = os.path.join(settings.BASE_DIR, "static", "sw.js")
    try:
        with open(sw_path, "r", encoding="utf-8") as f:
            content = f.read()
        response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
        response["Service-Worker-Allowed"] = "/"
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
    except FileNotFoundError:
        raise Http404("Service worker not found")


def offline_view(request):
    """
    Render offline fallback view when internet connection drops.
    """
    return render(request, "offline.html", status=200)


def app_download_view(request):
    """
    Dedicated Mobile App Landing Page showcasing app features,
    one-click install, and step-by-step guides for Android & iOS.
    """
    return render(request, "app_download.html")


def download_app_shortcut(request):
    """
    Download a native Desktop App launcher (.bat) that launches Takshashila University
    in standalone Chrome/Edge App Mode with no browser address bars.
    """
    host = request.get_host()
    scheme = request.scheme
    url = f"{scheme}://{host}/"
    content = f"""@echo off
title Takshashila University App
start chrome --app="{url}" 2>nul
if %errorlevel% neq 0 (
    start msedge --app="{url}" 2>nul
)
if %errorlevel% neq 0 (
    start "" "{url}"
)
"""
    response = HttpResponse(content, content_type="application/x-bat")
    response["Content-Disposition"] = 'attachment; filename="Takshashila-App.bat"'
    return response

