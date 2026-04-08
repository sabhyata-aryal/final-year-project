from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Report


class RoleAccessTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher1',
            email='teacher@nccs.edu',
            password='StrongPass123!',
        )
        self.teacher.profile.role = 'teacher'
        self.teacher.profile.save()

        self.student = User.objects.create_user(
            username='student1',
            email='student@nccs.edu',
            password='StrongPass123!',
        )
        self.student.profile.role = 'student'
        self.student.profile.save()

    def test_teacher_login_redirects_to_teacher_dashboard(self):
        response = self.client.post(
            reverse('login'),
            {'email': 'teacher@nccs.edu', 'password': 'StrongPass123!'},
        )
        self.assertRedirects(
            response,
            reverse('dashboard_redirect'),
            fetch_redirect_response=False,
        )

        follow_response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(follow_response, reverse('teacher_dashboard'))

    def test_student_cannot_access_teacher_upload_route(self):
        self.client.login(username='student1', password='StrongPass123!')
        response = self.client.get(reverse('upload_report'))
        self.assertEqual(response.status_code, 403)

    def test_student_scan_does_not_store_report(self):
        self.client.login(username='student1', password='StrongPass123!')
        upload = SimpleUploadedFile('essay.docx', b'placeholder content')

        with patch('reports.views.extract_uploaded_text', return_value='student draft text'):
            response = self.client.post(
                reverse('scan_document'),
                {'title': 'Essay', 'file': upload},
            )

        self.assertRedirects(response, reverse('scan_result'))
        self.assertEqual(Report.objects.count(), 0)

    def test_teacher_upload_creates_repository_report(self):
        self.client.login(username='teacher1', password='StrongPass123!')
        upload = SimpleUploadedFile('repo.docx', b'repository content')

        with patch('reports.views.extract_text', return_value='teacher repository text'):
            response = self.client.post(
                reverse('upload_report'),
                {'title': 'Repo', 'file': upload},
            )

        self.assertRedirects(response, reverse('upload_success'))
        self.assertEqual(Report.objects.filter(report_type='past').count(), 1)
