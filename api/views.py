from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from expenses.models import Expense, ExpenseSplit
from expenses.services import get_group_balances, simplify_debts
from groups.models import Group, Membership

from .serializers import ExpenseSerializer, GroupDetailSerializer, GroupSerializer


def get_member_group(user, group_id):
    """The group, if this user is a member; otherwise a 404."""
    return get_object_or_404(Group, id=group_id, memberships__user=user)


class GroupListView(generics.ListAPIView):
    """GET /api/groups/ - the groups you belong to, with your balance in each."""
    serializer_class = GroupSerializer

    def get_queryset(self):
        return (
            Group.objects
            .annotate(member_count=Count('memberships'))
            .filter(memberships__user=self.request.user)
            .order_by('-created_at')
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['balances'] = {
            group.id: get_group_balances(group).get(self.request.user)
            for group in self.get_queryset()
        }
        return context


class GroupDetailView(generics.RetrieveAPIView):
    """GET /api/groups/<id>/ - one group with its members."""
    serializer_class = GroupDetailSerializer
    lookup_url_kwarg = 'group_id'

    def get_queryset(self):
        return Group.objects.filter(memberships__user=self.request.user).prefetch_related('memberships__user')


class ExpenseListCreateView(generics.ListCreateAPIView):
    """GET /api/groups/<id>/expenses/ - list expenses. POST - add one."""
    serializer_class = ExpenseSerializer

    def get_group(self):
        return get_member_group(self.request.user, self.kwargs['group_id'])

    def get_queryset(self):
        return (
            self.get_group().expenses
            .select_related('paid_by')
            .prefetch_related('splits__user')
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['group'] = self.get_group()
        return context

    def perform_create(self, serializer):
        splits = serializer.validated_data.pop('calculated_splits')
        with transaction.atomic():
            expense = serializer.save(group=self.get_group(), created_by=self.request.user)
            ExpenseSplit.objects.bulk_create([
                ExpenseSplit(expense=expense, user=user, share_amount=share)
                for user, share in splits.items()
                if share > 0
            ])


class BalanceView(APIView):
    """GET /api/groups/<id>/balances/ - everyone's balance and suggested payments."""

    def get(self, request, group_id):
        group = get_member_group(request.user, group_id)
        balances = get_group_balances(group)
        return Response({
            'balances': [
                {'user': user.username, 'balance': str(amount)}
                for user, amount in balances.items()
            ],
            'suggested_payments': [
                {'from': payer.username, 'to': receiver.username, 'amount': str(amount)}
                for payer, receiver, amount in simplify_debts(balances)
            ],
        })
