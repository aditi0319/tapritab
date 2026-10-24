from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from expenses.models import Expense
from groups.models import Group, Membership


class ApiTests(APITestCase):
    def setUp(self):
        self.aman = User.objects.create_user('aman', 'aman@x.com', 'Chai@12345')
        self.riya = User.objects.create_user('riya', 'riya@x.com', 'Chai@12345')
        self.outsider = User.objects.create_user('zed', 'zed@x.com', 'Chai@12345')
        self.group = Group.objects.create(name='Chai Gang', created_by=self.aman)
        Membership.objects.create(user=self.aman, group=self.group, role=Membership.Role.ADMIN)
        Membership.objects.create(user=self.riya, group=self.group)
        self.expenses_url = reverse('api:expense_list', kwargs={'group_id': self.group.id})

    def test_login_required(self):
        self.assertEqual(self.client.get(reverse('api:group_list')).status_code, 403)

    def test_group_list_shows_only_my_groups(self):
        Group.objects.create(name='Not mine', created_by=self.outsider)
        self.client.force_authenticate(self.aman)
        response = self.client.get(reverse('api:group_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([g['name'] for g in response.data['results']], ['Chai Gang'])
        self.assertEqual(response.data['results'][0]['member_count'], 2)

    def test_create_equal_expense(self):
        self.client.force_authenticate(self.aman)
        response = self.client.post(self.expenses_url, {
            'title': 'Chai', 'amount': '45', 'paid_by': self.aman.id,
            'category': 'chai', 'split_type': 'equal',
            'shares': [{'user': self.aman.id}, {'user': self.riya.id}],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sum(Decimal(s['share_amount']) for s in response.data['splits']), Decimal('45'))

    def test_exact_split_must_add_up(self):
        self.client.force_authenticate(self.aman)
        response = self.client.post(self.expenses_url, {
            'title': 'Lunch', 'amount': '100', 'paid_by': self.aman.id,
            'category': 'meal', 'split_type': 'exact',
            'shares': [{'user': self.aman.id, 'value': '60'}, {'user': self.riya.id, 'value': '30'}],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Expense.objects.exists())

    def test_cannot_split_with_outsider(self):
        self.client.force_authenticate(self.aman)
        response = self.client.post(self.expenses_url, {
            'title': 'Chai', 'amount': '20', 'paid_by': self.aman.id,
            'category': 'chai', 'split_type': 'equal',
            'shares': [{'user': self.outsider.id}],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_outsider_gets_404(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.expenses_url).status_code, 404)
        self.assertEqual(self.client.get(reverse('api:balances', kwargs={'group_id': self.group.id})).status_code, 404)

    def test_balances_and_suggestions(self):
        self.client.force_authenticate(self.aman)
        self.client.post(self.expenses_url, {
            'title': 'Chai', 'amount': '40', 'paid_by': self.aman.id,
            'category': 'chai', 'split_type': 'equal',
            'shares': [{'user': self.aman.id}, {'user': self.riya.id}],
        }, format='json')
        response = self.client.get(reverse('api:balances', kwargs={'group_id': self.group.id}))
        self.assertEqual(response.data['suggested_payments'], [{'from': 'riya', 'to': 'aman', 'amount': '20.00'}])
