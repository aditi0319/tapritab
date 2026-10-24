from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from expenses.models import Expense, ExpenseSplit

from .models import Group, Membership

PASSWORD = 'Chai@12345'


class GroupTests(TestCase):
    def setUp(self):
        self.aman = User.objects.create_user('aman', 'aman@x.com', PASSWORD)
        self.riya = User.objects.create_user('riya', 'riya@x.com', PASSWORD)
        self.client.login(username='aman', password=PASSWORD)

    def create_group(self):
        self.client.post(reverse('groups:create'), {'name': 'Chai Gang', 'emoji': '☕'})
        return Group.objects.get()

    def test_creator_becomes_admin(self):
        group = self.create_group()
        membership = Membership.objects.get(group=group, user=self.aman)
        self.assertEqual(membership.role, Membership.Role.ADMIN)

    def test_non_member_gets_404(self):
        group = self.create_group()
        self.client.login(username='riya', password=PASSWORD)
        response = self.client.get(reverse('groups:detail', kwargs={'group_id': group.id}))
        self.assertEqual(response.status_code, 404)

    def test_join_with_invite_link(self):
        group = self.create_group()
        self.client.login(username='riya', password=PASSWORD)
        self.client.post(reverse('groups:join', kwargs={'invite_code': group.invite_code}))
        self.assertTrue(Membership.objects.filter(group=group, user=self.riya).exists())

    def test_reset_invite_link_kills_old_link(self):
        group = self.create_group()
        old_code = group.invite_code
        self.client.post(reverse('groups:regenerate_invite', kwargs={'group_id': group.id}))
        self.client.login(username='riya', password=PASSWORD)
        response = self.client.get(reverse('groups:join', kwargs={'invite_code': old_code}))
        self.assertEqual(response.status_code, 404)

    def test_member_count_counts_everyone(self):
        group = self.create_group()
        Membership.objects.create(group=group, user=self.riya)
        response = self.client.get(reverse('groups:list'))
        self.assertEqual(response.context['groups'][0].member_count, 2)

    def test_cannot_leave_with_unsettled_balance(self):
        group = self.create_group()
        Membership.objects.create(group=group, user=self.riya)
        expense = Expense.objects.create(
            group=group, title='Chai', amount=Decimal('20'), paid_by=self.aman, created_by=self.aman,
        )
        ExpenseSplit.objects.create(expense=expense, user=self.riya, share_amount=Decimal('20'))

        self.client.login(username='riya', password=PASSWORD)
        self.client.post(reverse('groups:leave', kwargs={'group_id': group.id}))
        self.assertTrue(Membership.objects.filter(group=group, user=self.riya).exists())

    def test_only_admin_can_remove_members(self):
        group = self.create_group()
        Membership.objects.create(group=group, user=self.riya)
        self.client.login(username='riya', password=PASSWORD)
        self.client.post(reverse('groups:remove_member', kwargs={'group_id': group.id, 'user_id': self.aman.id}))
        self.assertTrue(Membership.objects.filter(group=group, user=self.aman).exists())
