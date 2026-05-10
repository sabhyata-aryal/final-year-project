from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Report
from .utils import UNSUPPORTED_FILE_FORMAT_MESSAGE
from .views import build_similarity_result, get_similarity_classification


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

    def test_scan_rejects_unsupported_file_format(self):
        self.client.login(username='student1', password='StrongPass123!')
        upload = SimpleUploadedFile('essay.txt', b'plain text content', content_type='text/plain')

        response = self.client.post(
            reverse('scan_document'),
            {'title': 'Essay', 'file': upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(UNSUPPORTED_FILE_FORMAT_MESSAGE, response.context['form'].errors['file'])

    def test_teacher_upload_rejects_unsupported_file_format(self):
        self.client.login(username='teacher1', password='StrongPass123!')
        upload = SimpleUploadedFile('repo.txt', b'plain text content', content_type='text/plain')

        response = self.client.post(
            reverse('upload_report'),
            {'title': 'Repo', 'file': upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(UNSUPPORTED_FILE_FORMAT_MESSAGE, response.context['form'].errors['file'])
        self.assertEqual(Report.objects.filter(report_type='past').count(), 0)


class SimilarityResultTests(TestCase):
    def test_similarity_classification_boundaries(self):
        cases = [
            (0, 'Low (0-20%)', 'badge-low'),
            (20, 'Low (0-20%)', 'badge-low'),
            (21, 'Moderate (21-40%)', 'badge-moderate'),
            (40, 'Moderate (21-40%)', 'badge-moderate'),
            (41, 'High (41-70%)', 'badge-high'),
            (70, 'High (41-70%)', 'badge-high'),
            (71, 'Very High (71-100%)', 'badge-very-high'),
            (100, 'Very High (71-100%)', 'badge-very-high'),
        ]

        for score, expected_label, expected_badge in cases:
            with self.subTest(score=score):
                classification = get_similarity_classification(score)
                self.assertEqual(classification['label'], expected_label)
                self.assertEqual(classification['badge_class'], expected_badge)

    def test_build_similarity_result_sorts_descending_and_marks_top_match(self):
        Report.objects.create(
            title='Exact Match',
            report_type='past',
            file=SimpleUploadedFile('exact.docx', b'exact-bytes'),
            content='alpha beta gamma delta epsilon',
        )
        Report.objects.create(
            title='Partial Match',
            report_type='past',
            file=SimpleUploadedFile('partial.docx', b'partial-bytes'),
            content='alpha beta gamma delta zeta',
        )
        Report.objects.create(
            title='Low Match',
            report_type='past',
            file=SimpleUploadedFile('low.docx', b'low-bytes'),
            content='one two three four five',
        )

        result_data = build_similarity_result('Submission', 'alpha beta gamma delta epsilon')

        self.assertEqual(result_data['result'], 100.0)
        self.assertEqual(result_data['classification_label'], 'Very High (71-100%)')
        self.assertEqual(result_data['classification_badge_class'], 'badge-very-high')
        self.assertEqual(result_data['repository_size'], 3)

        similarity_table = result_data['similarity_table']
        scores = [item['similarity'] for item in similarity_table]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(similarity_table[0]['past_report_name'], 'exact.docx')
        self.assertTrue(similarity_table[0].get('is_top_match'))
        self.assertFalse(similarity_table[1].get('is_top_match', False))
        self.assertFalse(similarity_table[2].get('is_top_match', False))

    def test_build_similarity_result_without_repository_reports(self):
        result_data = build_similarity_result('Submission', 'alpha beta gamma delta epsilon')

        self.assertIsNone(result_data['result'])
        self.assertEqual(result_data['classification_label'], 'No Classification')
        self.assertEqual(result_data['classification_badge_class'], 'badge-none')
        self.assertEqual(result_data['similarity_table'], [])
        self.assertEqual(result_data['repository_size'], 0)
