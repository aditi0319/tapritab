from django import forms

from .models import Group


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ('name', 'emoji')
        labels = {'name': 'Group name', 'emoji': 'Icon'}
        help_texts = {'emoji': 'One emoji, like ☕ 🥟 🍱 🍪'}