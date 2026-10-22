from django.db import models
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone

from groups.models import Group

# Create your models here.

class Expense(models.Model):
    class Category(models.TextChoices):
        CHAI = 'chai','☕ Chai'
        SNACKS = 'snacks', '🥟 Snacks'
        MEAL = 'meal', '🍱 Meal'
        OTHER = 'other', '📦 Other'

    class SplitType(models.TextChoices):
        EQUAL = 'equal','Equal'
        EXACT = 'exact', 'Exact amounts'
        PERCENT = 'percent', 'Percentage'

    group = models.ForeignKey(Group,
    on_delete=models.CASCADE, 
    related_name ='expenses')   
    title = models.CharField(max_length=100)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    ) 
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='expenses_paid',
    )
    category = models.CharField(max_length=10,
               choices=Category.choices,
               default = Category.CHAI)
    split_type = models.CharField(max_length=10,
                choices= SplitType.choices,
                default=SplitType.EQUAL)
    date = models.DateField(default=timezone.localdate)
    receipt = models.ImageField(upload_to='receipts/',
                                 blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null =True,
        related_name='expenses_created',)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date','-created_at']
    def __str__(self):
        return f'{self.title} - ₹{self.amount} '

class ExpenseSplit(models.Model):
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE,
        related_name='splits'
    )    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='expense_splits',
    )
    share_amount = models.DecimalField(max_digits=10,
                                       decimal_places=2)

    class Meta:
        constraints=[
            models.UniqueConstraint(fields=['expense','user'],
                                    name='unique_split_per_user'),

        ] 

    def __str__(self):
            return f'{self.usr.username} owes ₹{self.share_amount} for {self.expense.title}'


class Settlement(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending','Pending'
        CONFIRMED = 'confirmed', 'Confirmed'

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='settlements')
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='settlements_paid',
    )  
    receiver =models.ForeignKey(
        settings.AUTH_USER_MODEL,
            on_delete=models.PROTECT,
        related_name='settlements_recieved',)

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    status = models.CharField(
        max_length=10,choices=Status.choices, 
        default=Status.PENDING
    )
    note = models.CharField(max_length=200,blank=True)
    created_at =models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering =['-created_at']
        constraints =[
            models.CheckConstraint(
                condition=~models.Q(payer=models.F('receiver')),
                name = 'payer_not_received',
            ),
        ]

    def __str__(self):
        return f'{self.payer.username} paid {self.receiver.username} ₹{self.amount}'


        
      



