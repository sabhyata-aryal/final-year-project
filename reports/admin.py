from django.contrib import admin
from .models import Report, UserProfile

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'report_type', 'uploaded_at', 'file')
    list_filter = ('report_type',)
    ordering = ('-uploaded_at',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')
