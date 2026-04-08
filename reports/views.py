import os
import tempfile

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .decorators import role_required
from .forms import LoginForm, RegistrationForm, ScanDocumentForm, TeacherUploadForm
from .models import Report, UserProfile
from .utils import calculate_jaccard_similarity, extract_text


PLAGIARISM_THRESHOLD = 30.0
SCAN_RESULT_SESSION_KEY = 'latest_scan_result'


def get_user_role(user):
    if not user.is_authenticated:
        return None
    return getattr(getattr(user, 'profile', None), 'role', None)


def build_similarity_result(submitted_name, submitted_text):
    past_reports = Report.objects.filter(report_type='past')
    similarity_table = []
    highest_similarity = 0

    for past_report in past_reports:
        similarity_percentage = calculate_jaccard_similarity(submitted_text, past_report.content)
        similarity_table.append({
            'past_report_name': past_report.file.name.split('/')[-1],
            'similarity': similarity_percentage,
        })
        highest_similarity = max(highest_similarity, similarity_percentage)

    return {
        'report1_name': submitted_name,
        'result': highest_similarity if past_reports.exists() else None,
        'similarity_table': similarity_table,
        'repository_size': past_reports.count(),
    }


def extract_uploaded_text(uploaded_file):
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name

        return extract_text(temp_file_path)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def home(request):
    total_reports_uploaded = Report.objects.count()
    reports_checked = Report.objects.filter(report_type='new').count()
    repository_size = Report.objects.filter(report_type='past').count()

    past_reports = list(Report.objects.filter(report_type='past').only('content'))
    new_reports = list(Report.objects.filter(report_type='new').only('content'))

    plagiarism_cases_detected = 0
    for submitted_report in new_reports:
        highest_similarity = 0
        for repository_report in past_reports:
            similarity = calculate_jaccard_similarity(
                submitted_report.content,
                repository_report.content,
            )
            if similarity > highest_similarity:
                highest_similarity = similarity

        if highest_similarity >= PLAGIARISM_THRESHOLD:
            plagiarism_cases_detected += 1

    context = {
        'total_reports_uploaded': total_reports_uploaded,
        'reports_checked': reports_checked,
        'plagiarism_cases_detected': plagiarism_cases_detected,
        'repository_size': repository_size,
        'user_role': get_user_role(request.user),
    }
    return render(request, 'reports/home.html', context)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='reports.backends.EmailBackend')
        messages.success(request, 'Registration successful.')
        return redirect('dashboard_redirect')

    return render(request, 'reports/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = authenticate(request, email=email, password=password)

        if user is None:
            form.add_error(None, 'Invalid email or password.')
        else:
            login(request, user)
            return redirect('dashboard_redirect')

    return render(request, 'reports/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required
def dashboard_redirect(request):
    if get_user_role(request.user) == UserProfile.ROLE_TEACHER:
        return redirect('teacher_dashboard')
    if get_user_role(request.user) == UserProfile.ROLE_STUDENT:
        return redirect('student_dashboard')
    return redirect('home')


@role_required(UserProfile.ROLE_TEACHER)
def teacher_dashboard(request):
    context = {
        'repository_size': Report.objects.filter(report_type='past').count(),
        'latest_result': request.session.get(SCAN_RESULT_SESSION_KEY),
    }
    return render(request, 'reports/teacher_dashboard.html', context)


@role_required(UserProfile.ROLE_STUDENT)
def student_dashboard(request):
    return render(
        request,
        'reports/student_dashboard.html',
        {'latest_result': request.session.get(SCAN_RESULT_SESSION_KEY)},
    )


def landing_scan_redirect(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to scan documents')
        return redirect('login')
    return redirect('scan_document')


@role_required(UserProfile.ROLE_TEACHER)
def upload_report(request):
    form = TeacherUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        report = form.save(commit=False)
        report.report_type = 'past'
        report.save()
        report.content = extract_text(report.file.path)
        report.save(update_fields=['content'])
        messages.success(request, 'Document uploaded to the repository successfully.')
        return redirect('upload_success')

    return render(
        request,
        'reports/upload.html',
        {
            'form': form,
            'page_title': 'Upload Document',
            'page_heading': 'Upload document to repository',
            'page_description': 'Teacher uploads are stored permanently and used for future comparisons.',
            'submit_label': 'Upload Document',
            'dashboard_url': 'teacher_dashboard',
            'mode': 'upload',
        },
    )


@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
def scan_document(request):
    form = ScanDocumentForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        uploaded_file = form.cleaned_data['file']
        submitted_name = form.cleaned_data['title'] or uploaded_file.name
        extracted_text = extract_uploaded_text(uploaded_file)
        request.session[SCAN_RESULT_SESSION_KEY] = build_similarity_result(submitted_name, extracted_text)
        messages.success(request, 'Scan completed successfully.')
        return redirect('scan_result')

    return render(
        request,
        'reports/upload.html',
        {
            'form': form,
            'page_title': 'Scan Document',
            'page_heading': 'Scan document for plagiarism',
            'page_description': 'Scanned files are temporary and are not added to the repository database.',
            'submit_label': 'Scan Document',
            'dashboard_url': 'dashboard_redirect',
            'mode': 'scan',
        },
    )


@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
def compare_reports(request):
    result_data = request.session.get(
        SCAN_RESULT_SESSION_KEY,
        {
            'result': None,
            'report1_name': '',
            'similarity_table': [],
            'repository_size': Report.objects.filter(report_type='past').count(),
        },
    )
    return render(request, 'reports/result.html', result_data)


@role_required(UserProfile.ROLE_TEACHER)
def upload_success(request):
    return render(request, 'reports/success.html')


@role_required(UserProfile.ROLE_TEACHER)
def repository(request):
    past_reports = Report.objects.filter(report_type='past').order_by('-uploaded_at')
    return render(request, 'reports/repository.html', {'past_reports': past_reports})
