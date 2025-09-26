"""
URL configuration for assessment_tool project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.views.generic import TemplateView

def robots_txt(request):
    return render(request, "robots.txt", content_type="text/plain")

urlpatterns = [
    path('', include(('apps.dashboard.urls', 'dashboard'), namespace='dashboard_root')),
    path('accounts/', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),
    path('assessments/', include(('apps.assessments.urls', 'assessments'), namespace='assessments')),
    path('dashboard/', include(('apps.dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('payments/', include(('apps.payments.urls', 'payments'), namespace='payments')),
    path('pdfexport/', include('apps.pdfexport.urls')),
    path('reports/', include(('apps.reports.urls', 'reports'), namespace='reports')),
    path('teams/', include(('apps.teams.urls', 'teams'), namespace='teams')),
    # Legal pages
    path('legal/privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('legal/terms/',   TemplateView.as_view(template_name='legal/terms.html'),   name='terms'),
    # Other
    path('alao/', admin.site.urls), #Admin Level Access Only
    path('robots.txt', robots_txt, name='robots_txt'),
    path('markdownx/', include('markdownx.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)