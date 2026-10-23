from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from .models import Expense
from .services import calculate_splits

User = get_user_model()

MAX_RECEIPT_SIZE = 2 * 1024 * 1024  # 2 MB


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ('title', 'amount', 'paid_by', 'category', 'split_type', 'date', 'receipt')
        labels = {'paid_by': 'Paid by', 'split_type': 'How to split'}
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.members = list(User.objects.filter(memberships__group=group).order_by('username'))
        self.fields['paid_by'].queryset = User.objects.filter(memberships__group=group)

        for member in self.members:
            self.fields[f'include_{member.id}'] = forms.BooleanField(
                required=False, initial=True, label=member.username,
            )
            self.fields[f'share_{member.id}'] = forms.DecimalField(
                required=False, min_value=Decimal('0'), max_digits=10, decimal_places=2,
                label=f'Share for {member.username}',
            )

    @property
    def main_fields(self):
        return [self[name] for name in self.Meta.fields]

    @property
    def member_rows(self):
        return [
            (member, self[f'include_{member.id}'], self[f'share_{member.id}'])
            for member in self.members
        ]

    def clean_receipt(self):
        receipt = self.cleaned_data.get('receipt')
        if receipt and receipt.size > MAX_RECEIPT_SIZE:
            raise forms.ValidationError('Receipt image must be smaller than 2 MB.')
        return receipt

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get('amount')
        split_type = cleaned.get('split_type')
        if amount is None or not split_type:
            return cleaned

        participants = [m for m in self.members if cleaned.get(f'include_{m.id}')]
        if not participants:
            raise forms.ValidationError('Select at least one person to split with.')

        values = None
        if split_type != Expense.SplitType.EQUAL:
            values = {}
            for member in participants:
                value = cleaned.get(f'share_{member.id}')
                if value is None:
                    raise forms.ValidationError(f'Enter a value for {member.username}.')
                values[member] = value
            total = sum(values.values())

            if split_type == Expense.SplitType.EXACT and total != amount:
                raise forms.ValidationError(
                    f'Exact amounts add up to ₹{total}, but the expense is ₹{amount}.'
                )
            if split_type == Expense.SplitType.PERCENT and total != 100:
                raise forms.ValidationError(
                    f'Percentages add up to {total}%. They must add up to 100%.'
                )

        self.splits = calculate_splits(amount, split_type, participants, values)
        return cleaned