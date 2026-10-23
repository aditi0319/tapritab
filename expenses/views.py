from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from groups.models import Membership
from groups.views import get_membership_or_404

from .forms import ExpenseForm
from .models import Expense, ExpenseSplit


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