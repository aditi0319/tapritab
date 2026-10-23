from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from groups.models import Membership
from groups.views import get_membership_or_404

from .forms import ExpenseForm, SettlementForm
from .models import Expense, ExpenseSplit, Settlement
from .services import get_group_balances, simplify_debts


@login_required
def expense_create(request, group_id):
    membership = get_membership_or_404(request.user, group_id)
    group = membership.group

    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, group=group)
        if form.is_valid():
            with transaction.atomic():
                expense = form.save(commit=False)
                expense.group = group
                expense.created_by = request.user
                expense.save()
                ExpenseSplit.objects.bulk_create([
                    ExpenseSplit(expense=expense, user=user, share_amount=share)
                    for user, share in form.splits.items()
                    if share > 0
                ])
            messages.success(request, f'Added "{expense.title}" for ₹{expense.amount}.')
            return redirect('groups:detail', group_id=group.id)
    else:
        form = ExpenseForm(group=group, initial={'paid_by': request.user})

    return render(request, 'expenses/expense_form.html', {'form': form, 'group': group})


@login_required
@require_POST
def expense_delete(request, group_id, expense_id):
    membership = get_membership_or_404(request.user, group_id)
    expense = get_object_or_404(Expense, id=expense_id, group_id=group_id)

    if expense.created_by != request.user and membership.role != Membership.Role.ADMIN:
        messages.error(request, 'Only the person who added this expense or the group admin can delete it.')
    else:
        title = expense.title
        expense.delete()
        messages.success(request, f'Deleted "{title}".')
    return redirect('groups:detail', group_id=group_id)


def build_upi_link(receiver, amount):
    profile = getattr(receiver, 'profile', None)
    if not profile or not profile.upi_id:
        return ''
    query = urlencode({
        'pa': profile.upi_id,
        'pn': receiver.get_full_name() or receiver.username,
        'am': f'{amount:.2f}',
        'cu': 'INR',
        'tn': 'TapriTab settle up',
    })
    return f'upi://pay?{query}'


@login_required
def settle_up(request, group_id):
    membership = get_membership_or_404(request.user, group_id)
    group = membership.group

    balances = get_group_balances(group)
    pending = (
        group.settlements
        .filter(status=Settlement.Status.PENDING)
        .select_related('payer', 'receiver')
    )
    pending_pairs = {(s.payer_id, s.receiver_id) for s in pending}

    suggestions = []
    for payer, receiver, amount in simplify_debts(balances):
        suggestions.append({
            'payer': payer,
            'receiver': receiver,
            'amount': amount,
            'upi_link': build_upi_link(receiver, amount),
            'upi_id': getattr(getattr(receiver, 'profile', None), 'upi_id', ''),
            'is_pending': (payer.id, receiver.id) in pending_pairs,
        })

    history = (
        group.settlements
        .filter(status=Settlement.Status.CONFIRMED)
        .select_related('payer', 'receiver')[:20]
    )

    return render(request, 'expenses/settle_up.html', {
        'group': group,
        'balances': [
            {'user': member, 'amount': amount, 'abs_amount': abs(amount)}
            for member, amount in sorted(balances.items(), key=lambda item: item[1], reverse=True)
        ],
        'suggestions': suggestions,
        'pending': pending,
        'history': history,
    })


@login_required
@require_POST
def settlement_create(request, group_id):
    membership = get_membership_or_404(request.user, group_id)
    group = membership.group
    form = SettlementForm(request.POST, group=group, user=request.user)

    if form.is_valid():
        settlement = form.save(commit=False)
        settlement.group = group
        if settlement.receiver == request.user:
            settlement.status = Settlement.Status.CONFIRMED
            settlement.confirmed_at = timezone.now()
            messages.success(request, f'Recorded ₹{settlement.amount} received from {settlement.payer.username}.')
        else:
            messages.success(
                request,
                f'Payment of ₹{settlement.amount} recorded. Waiting for {settlement.receiver.username} to confirm.',
            )
        settlement.save()
    else:
        for error in form.non_field_errors() or ['Could not record this payment.']:
            messages.error(request, error)
    return redirect('expenses:settle_up', group_id=group.id)


@login_required
@require_POST
def settlement_confirm(request, group_id, settlement_id):
    get_membership_or_404(request.user, group_id)
    settlement = get_object_or_404(
        Settlement, id=settlement_id, group_id=group_id,
        receiver=request.user, status=Settlement.Status.PENDING,
    )
    settlement.status = Settlement.Status.CONFIRMED
    settlement.confirmed_at = timezone.now()
    settlement.save(update_fields=['status', 'confirmed_at'])
    messages.success(request, f'Confirmed ₹{settlement.amount} from {settlement.payer.username}. ✅')
    return redirect('expenses:settle_up', group_id=group_id)


@login_required
@require_POST
def settlement_cancel(request, group_id, settlement_id):
    get_membership_or_404(request.user, group_id)
    settlement = get_object_or_404(
        Settlement, id=settlement_id, group_id=group_id, status=Settlement.Status.PENDING,
    )
    if request.user not in (settlement.payer, settlement.receiver):
        messages.error(request, 'You cannot change this payment.')
    else:
        settlement.delete()
        messages.info(request, 'Pending payment removed.')
    return redirect('expenses:settle_up', group_id=group_id)