import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('upi_id', 'phone', 'avatar')
        labels = {'upi_id': 'UPI ID'}
        help_texts = {'upi_id': 'Example: aditi@okaxis'}

    def clean_upi_id(self):
        upi_id = self.cleaned_data['upi_id'].strip()
        if upi_id and not re.fullmatch(r'[\w.\-]{2,256}@[a-zA-Z]{2,64}', upi_id):
            raise forms.ValidationError('Enter a valid UPI ID, like name@bank.')
        return upi_id