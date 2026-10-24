from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from expenses.models import Expense, ExpenseSplit
from expenses.services import calculate_splits
from groups.models import Group, Membership

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username')


class MemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ('user', 'role', 'joined_at')


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    my_balance = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ('id', 'name', 'emoji', 'member_count', 'my_balance', 'created_at')

    def get_my_balance(self, group):
        balances = self.context.get('balances', {})
        return str(balances.get(group.id, Decimal('0.00')))


class GroupDetailSerializer(serializers.ModelSerializer):
    members = MemberSerializer(source='memberships', many=True, read_only=True)

    class Meta:
        model = Group
        fields = ('id', 'name', 'emoji', 'invite_code', 'created_at', 'members')


class SplitSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ('user', 'share_amount')


class ShareInputSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class ExpenseSerializer(serializers.ModelSerializer):
    paid_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    splits = SplitSerializer(many=True, read_only=True)
    shares = ShareInputSerializer(many=True, write_only=True)

    class Meta:
        model = Expense
        fields = (
            'id', 'title', 'amount', 'paid_by', 'category', 'split_type', 'date',
            'created_at', 'splits', 'shares',
        )
        read_only_fields = ('created_at',)

    def validate(self, data):
        group = self.context['group']
        members = {m.id: m for m in User.objects.filter(memberships__group=group)}

        if data['paid_by'].id not in members:
            raise serializers.ValidationError({'paid_by': 'Payer must be a member of this group.'})

        shares = data.pop('shares')
        if not shares:
            raise serializers.ValidationError({'shares': 'Add at least one person to split with.'})

        participants, values = [], {}
        for share in shares:
            user = members.get(share['user'])
            if user is None:
                raise serializers.ValidationError({'shares': f"User {share['user']} is not in this group."})
            participants.append(user)
            if data['split_type'] != Expense.SplitType.EQUAL:
                if share.get('value') is None:
                    raise serializers.ValidationError({'shares': f'Enter a value for {user.username}.'})
                values[user] = share['value']

        if data['split_type'] == Expense.SplitType.EXACT and sum(values.values()) != data['amount']:
            raise serializers.ValidationError({'shares': 'Exact amounts must add up to the expense amount.'})
        if data['split_type'] == Expense.SplitType.PERCENT and sum(values.values()) != 100:
            raise serializers.ValidationError({'shares': 'Percentages must add up to 100.'})

        data['calculated_splits'] = calculate_splits(
            data['amount'], data['split_type'], participants, values or None,
        )
        return data
