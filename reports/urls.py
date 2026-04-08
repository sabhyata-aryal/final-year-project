from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('scan-redirect/', views.landing_scan_redirect, name='landing_scan_redirect'),
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('upload/', views.upload_report, name='upload_report'),
    path('scan/', views.scan_document, name='scan_document'),
    path('repository/', views.repository, name='repository'),
    path('compare/', views.compare_reports, name='scan_result'),
    path('success/', views.upload_success, name='upload_success'),
]
