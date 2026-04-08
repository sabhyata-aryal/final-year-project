from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from .models import Report, UserProfile
from .utils import validate_unique_past_report


def build_unique_username(email):
    base_username = email.split('@')[0].strip() or 'user'
    candidate = base_username
    suffix = 1

    while User.objects.filter(username=candidate).exists():
        candidate = f'{base_username}{suffix}'
        suffix += 1

    return candidate


class RegistrationForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match.')

        if password1:
            validate_password(password1, user=User(email=cleaned_data.get('email', '')))

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = build_unique_username(user.email)
        user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()
            user.profile.role = self.cleaned_data['role']
            user.profile.save()

        return user


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class TeacherUploadForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['title', 'file']

    def clean(self):
        cleaned_data = super().clean()
        uploaded_file = cleaned_data.get('file')

        if uploaded_file:
            existing_past_reports = Report.objects.filter(report_type='past').only('file')
            validate_unique_past_report(uploaded_file, existing_past_reports)

        return cleaned_data


class ScanDocumentForm(forms.Form):
    title = forms.CharField(max_length=255, required=False)
    file = forms.FileField()
