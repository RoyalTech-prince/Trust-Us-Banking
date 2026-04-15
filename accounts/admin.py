from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import BankUser, License

@admin.register(BankUser)
class BankUserAdmin(UserAdmin):
    # 1. This adds custom fields to the EDIT page (after the user is created)
    fieldsets = UserAdmin.fieldsets + (
        ('Banking & Biometrics', {
            'fields': ('balance', 'face_encoding_sample'),
        }),
    )

    # 2. This adds custom fields to the INITIAL ADD page (The screen in your screenshot)
    # This is what will finally show the "Choose File" button for Egbensi/Princolo
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Initial Banking Setup', {
            'classes': ('wide',),
            'fields': ('balance', 'face_encoding_sample'),
        }),
    )

    list_display = ('username', 'email', 'balance', 'is_active')
    search_fields = ('username', 'email')

@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('user', 'license_key', 'expiry_date', 'is_active')
    list_filter = ('is_active', 'expiry_date')
    search_fields = ('user__username', 'license_key')