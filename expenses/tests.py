from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from groups.models import Group, Membership

from .models import Expense, ExpenseSplit, Settlement
from .services import calculate_splits, distribute, get_group_balances, simplify_debts

D = Decimal
PASSWORD = 'Chai@12345'


class DistributeTests(TestCase):
    """Pure maths: no database needed, but TestCase keeps it simple."""

    def test_equal_split_never_loses_a_paisa(self):
        shares = distribute(D('100'), {'a': D('1'), 'b': D('1'), 'c': D('1')})
        self.assertEqual(sum(shares.values()), D('100'))
        self.assertEqual(sorted(shares.values()), [D('33.33'), D('33.33'), D('33.34')])

    def test_leftover_goes_to_largest_remainder(self):
        shares = distribute(D('10'), {'a': D('33.33'), 'b': D('33.33'), 'c': D('33.34')})
        self.assertEqual(shares['c'], D('3.34'))
        self.assertEqual(sum(shares.values()), D('10'))

    def test_tiny_amount_split_many_ways(self):
        shares = distribute(D('0.05'), {name: D('1') for name in 'abcdefg'})
        self.assertEqual(sum(shares.values()), D('0.05'))
        self.assertTrue(all(share >= 0 for share in shares.values()))

    def test_exact_split_is_returned_as_given(self):
        values = {'a': D('70'), 'b': D('30')}
        self.assertEqual(calculate_splits(D('100'), 'exact', ['a', 'b'], values), values)


class SimplifyDebtsTests(TestCase):
    def test_two_debtors_one_creditor(self):
        payments = simplify_debts({'aman': D('60'), 'karan': D('-30'), 'neha': D('-30')})
        self.assertEqual(len(payments), 2)
        self.assertTrue(all(receiver == 'aman' for _, receiver, _ in payments))

    def test_chain_collapses_to_one_payment(self):
        payments = simplify_debts({'a': D('-50'), 'b': D('0'), 'c': D('50')})
        self.assertEqual(payments, [('a', 'c', D('50'))])

    def test_never_more_than_n_minus_one_payments(self):
        balances = {'a': D('50'), 'b': D('30'), 'c': D('-40'), 'd': D('-40')}
        payments = simplify_debts(balances)
        self.assertLessEqual(len(payments), len(balances) - 1)
        # Applying the payments settles everyone.
        for payer, receiver, amount in payments:
            balances[payer] += amount
            balances[receiver] -= amount
        self.assertTrue(all(value == 0 for value in balances.values()))

    def test_everyone_settled_means_no_payments(self):
        self.assertEqual(simplify_debts({'a': D('0'), 'b': D('0')}), [])


class GroupTestMixin:
    """Creates a group with aman (admin), riya and karan, plus an outsider."""

    def setUp(self):
        self.aman = User.objects.create_user('aman', 'aman@x.com', PASSWORD)
        self.riya = User.objects.create_user('riya', 'riya@x.com', PASSWORD)
        self.karan = User.objects.create_user('karan', 'karan@x.com', PASSWORD)
        self.outsider = User.objects.create_user('zed', 'zed@x.com', PASSWORD)
        self.group = Group.objects.create(name='Chai Gang', created_by=self.aman)
        Membership.objects.create(user=self.aman, group=self.group, role=Membership.Role.ADMIN)
        Membership.objects.create(user=self.riya, group=self.group)
        Membership.objects.create(user=self.karan, group=self.group)

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def add_expense(self, payer, amount, shares):
        expense = Expense.objects.create(
            group=self.group, title='Chai', amount=D(amount), paid_by=payer,
            created_by=payer, date=date(2026, 10, 24),
        )
        for user, share in shares.items():
            ExpenseSplit.objects.create(expense=expense, user=user, share_amount=D(share))
        return expense


class BalanceTests(GroupTestMixin, TestCase):
    def test_balances_from_expenses(self):
        self.add_expense(self.aman, '90', {self.aman: '30', self.riya: '30', self.karan: '30'})
        balances = get_group_balances(self.group)
        self.assertEqual(balances[self.aman], D('60.00'))
        self.assertEqual(balances[self.riya], D('-30.00'))
        self.assertEqual(sum(balances.values()), 0)

    def test_only_confirmed_settlements_count(self):
        self.add_expense(self.aman, '90', {self.aman: '30', self.riya: '30', self.karan: '30'})
        Settlement.objects.create(group=self.group, payer=self.riya, receiver=self.aman, amount=D('30'))
        self.assertEqual(get_group_balances(self.group)[self.riya], D('-30.00'))

        Settlement.objects.filter(payer=self.riya).update(status=Settlement.Status.CONFIRMED)
        self.assertEqual(get_group_balances(self.group)[self.riya], D('0.00'))


class ExpenseViewTests(GroupTestMixin, TestCase):
    def url(self):
        return reverse('expenses:create', kwargs={'group_id': self.group.id})

    def form_data(self, **extra):
        data = {
            'title': 'Evening chai', 'amount': '100', 'paid_by': self.aman.id,
            'category': 'chai', 'split_type': 'equal', 'date': '2026-10-24',
        }
        for user in (self.aman, self.riya, self.karan):
            data[f'include_{user.id}'] = 'on'
        data.update(extra)
        return data

    def test_equal_split_is_saved_and_adds_up(self):
        self.login(self.aman)
        response = self.client.post(self.url(), self.form_data())
        self.assertEqual(response.status_code, 302)
        expense = Expense.objects.get()
        self.assertEqual(sum(s.share_amount for s in expense.splits.all()), D('100'))

    def test_exact_split_must_match_total(self):
        self.login(self.aman)
        data = self.form_data(split_type='exact', **{
            f'share_{self.aman.id}': '50', f'share_{self.riya.id}': '30', f'share_{self.karan.id}': '10',
        })
        response = self.client.post(self.url(), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'add up to')
        self.assertFalse(Expense.objects.exists())

    def test_non_member_cannot_open_the_form(self):
        self.login(self.outsider)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_payer_must_be_a_member(self):
        self.login(self.aman)
        self.client.post(self.url(), self.form_data(paid_by=self.outsider.id))
        self.assertFalse(Expense.objects.exists())

    def test_member_cannot_delete_someone_elses_expense(self):
        expense = self.add_expense(self.aman, '30', {self.aman: '15', self.riya: '15'})
        self.login(self.riya)
        self.client.post(reverse('expenses:delete', kwargs={'group_id': self.group.id, 'expense_id': expense.id}))
        self.assertTrue(Expense.objects.filter(id=expense.id).exists())

    def test_delete_requires_post(self):
        expense = self.add_expense(self.aman, '30', {self.aman: '15', self.riya: '15'})
        self.login(self.aman)
        url = reverse('expenses:delete', kwargs={'group_id': self.group.id, 'expense_id': expense.id})
        self.assertEqual(self.client.get(url).status_code, 405)


class SettlementViewTests(GroupTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.add_expense(self.aman, '90', {self.aman: '30', self.riya: '30', self.karan: '30'})
        self.record_url = reverse('expenses:settlement_create', kwargs={'group_id': self.group.id})

    def test_payer_records_pending_then_receiver_confirms(self):
        self.login(self.riya)
        self.client.post(self.record_url, {'payer': self.riya.id, 'receiver': self.aman.id, 'amount': '30'})
        settlement = Settlement.objects.get()
        self.assertEqual(settlement.status, Settlement.Status.PENDING)

        self.login(self.aman)
        self.client.post(reverse('expenses:settlement_confirm', kwargs={
            'group_id': self.group.id, 'settlement_id': settlement.id,
        }))
        settlement.refresh_from_db()
        self.assertEqual(settlement.status, Settlement.Status.CONFIRMED)
        self.assertEqual(get_group_balances(self.group)[self.riya], D('0.00'))

    def test_only_receiver_can_confirm(self):
        settlement = Settlement.objects.create(
            group=self.group, payer=self.riya, receiver=self.aman, amount=D('30'),
        )
        self.login(self.karan)
        response = self.client.post(reverse('expenses:settlement_confirm', kwargs={
            'group_id': self.group.id, 'settlement_id': settlement.id,
        }))
        self.assertEqual(response.status_code, 404)

    def test_cannot_record_payment_between_two_other_people(self):
        self.login(self.karan)
        self.client.post(self.record_url, {'payer': self.riya.id, 'receiver': self.aman.id, 'amount': '30'})
        self.assertFalse(Settlement.objects.exists())
