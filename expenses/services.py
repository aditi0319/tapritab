from decimal import ROUND_DOWN, Decimal

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