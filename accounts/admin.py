from django.contrib import admin
from .models import BankUser, Account

admin.site.register(BankUser)
admin.site.register(Account)