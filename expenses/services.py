from decimal import ROUND_DOWN, Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum

from .models import Expense, ExpenseSplit, Settlement

PAISA = Decimal('0.01')


def distribute(amount, weights):
    """Split `amount` in proportion to `weights` so the parts add up to exactly `amount`.

    weights: {user: Decimal}, e.g. {aman: 1, riya: 1} for equal, or percentages.
    Leftover paise go to the people whose exact share was rounded down the most.
    """
    total_weight = sum(weights.values())
    exact = {user: amount * weight / total_weight for user, weight in weights.items()}
    shares = {user: value.quantize(PAISA, rounding=ROUND_DOWN) for user, value in exact.items()}

    leftover_paise = int((amount - sum(shares.values())) / PAISA)
    by_remainder = sorted(shares, key=lambda user: exact[user] - shares[user], reverse=True)
    for user in by_remainder[:leftover_paise]:
        shares[user] += PAISA
    return shares


def calculate_splits(amount, split_type, participants, values=None):
    """Return {user: share_amount} for an expense."""
    if split_type == 'equal':
        return distribute(amount, {user: Decimal('1') for user in participants})
    if split_type == 'percent':
        return distribute(amount, values)
    if split_type == 'exact':
        return dict(values)
    raise ValueError(f'Unknown split type: {split_type}')


def get_group_balances(group):
    """Return {user: net_balance} for everyone in the group.

    Positive  -> the group owes them money (they get money back).
    Negative  -> they owe money to the group.
    Only CONFIRMED settlements count.
    """
    User = get_user_model()
    balances = {}

    def add(rows, user_key, sign):
        for row in rows:
            balances[row[user_key]] = balances.get(row[user_key], Decimal('0')) + sign * row['total']

    add(Expense.objects.filter(group=group)
        .values('paid_by').annotate(total=Sum('amount')), 'paid_by', 1)
    add(ExpenseSplit.objects.filter(expense__group=group)
        .values('user').annotate(total=Sum('share_amount')), 'user', -1)

    confirmed = Settlement.objects.filter(group=group, status=Settlement.Status.CONFIRMED)
    add(confirmed.values('payer').annotate(total=Sum('amount')), 'payer', 1)
    add(confirmed.values('receiver').annotate(total=Sum('amount')), 'receiver', -1)

    member_ids = set(group.memberships.values_list('user_id', flat=True))
    users = User.objects.in_bulk(member_ids | set(balances))
    return {
        users[user_id]: balances.get(user_id, Decimal('0')).quantize(PAISA)
        for user_id in users
    }


def simplify_debts(balances):
    """Greedy algorithm: fewest payments to settle everyone.

    Returns a list of (payer, receiver, amount).
    """
    creditors = sorted(((amt, u) for u, amt in balances.items() if amt > 0),
                       key=lambda pair: pair[0], reverse=True)
    debtors = sorted(((-amt, u) for u, amt in balances.items() if amt < 0),
                     key=lambda pair: pair[0], reverse=True)
    creditors = [list(pair) for pair in creditors]
    debtors = [list(pair) for pair in debtors]

    payments = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][0], creditors[j][0])
        payments.append((debtors[i][1], creditors[j][1], amount))
        debtors[i][0] -= amount
        creditors[j][0] -= amount
        if debtors[i][0] == 0:
            i += 1
        if creditors[j][0] == 0:
            j += 1
    return payments