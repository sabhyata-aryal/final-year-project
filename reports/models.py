import hashlib

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_TEACHER = 'teacher'
    ROLE_STUDENT = 'student'
    ROLE_CHOICES = [
        (ROLE_TEACHER, 'Teacher'),
        (ROLE_STUDENT, 'Student'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STUDENT)

    def __str__(self):
        return f'{self.user.email or self.user.username} ({self.role})'


class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        ('past', 'Past Report (Repository)'),
        ('new', 'New Submission'),
    ]

    title = models.CharField(max_length=255)
    report_type = models.CharField(max_length=10, choices=REPORT_TYPE_CHOICES)
    file = models.FileField(upload_to='reports/')
    file_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    content = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def _compute_file_hash(self):
        if not self.file:
            return None

        hasher = hashlib.sha256()

        # UploadedFile (e.g., InMemoryUploadedFile) supports chunks()
        if hasattr(self.file, 'chunks'):
            for chunk in self.file.chunks():
                hasher.update(chunk)
            try:
                self.file.seek(0)
            except Exception:
                pass
            return hasher.hexdigest()

        # Stored file field (FieldFile)
        try:
            with self.file.open('rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
        except Exception:
            return None

        return hasher.hexdigest()

    def save(self, *args, **kwargs):
        if self.report_type == 'past' and self.file:
            computed_hash = self._compute_file_hash()
            if computed_hash:
                self.file_hash = computed_hash

                duplicates = Report.objects.filter(report_type='past', file_hash=computed_hash).exclude(pk=self.pk)
                if duplicates.exists():
                    raise ValidationError('This file has already been uploaded.')

        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
