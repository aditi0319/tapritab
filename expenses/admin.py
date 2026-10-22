from django.contrib import admin

from .models import Expense, ExpenseSplit, Settlement

admin.site.register(Expense)
admin.site.register(ExpenseSplit)
admin.site.register(Settlement)