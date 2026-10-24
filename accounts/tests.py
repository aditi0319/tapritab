from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile


class AccountTests(TestCase):
    def register(self, username='neha', email='neha@x.com'):
        return self.client.post(reverse('accounts:register'), {
            'username': username, 'email': email,
            'password1': 'Chai@12345', 'password2': 'Chai@12345',
        })

    def test_register_creates_user_and_profile(self):
        self.register()
        user = User.objects.get(username='neha')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_duplicate_email_is_blocked_case_insensitive(self):
        self.register()
        self.client.logout()
        response = self.register(username='neha2', email='NEHA@x.com')
        self.assertContains(response, 'already exists')
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_upi_id_is_rejected(self):
        self.register()
        response = self.client.post(reverse('accounts:profile'), {'upi_id': 'not a upi', 'phone': ''})
        self.assertContains(response, 'valid UPI ID')

    def test_profile_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
