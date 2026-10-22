from django.db import models
from django.conf import settings
import uuid

class Group(models.Model):
    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=10, default='☕')
    invite_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_groups',
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through = 'Membership',
        related_name ='tapri_groups',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = 'Tapri group'
        verbose_name_plural = 'Tapri groups'

    def __str__(self):
        return f'{self.emoji}{self.name}'

class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = 'admin','Admin'
        Member = 'member','Member'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = 'memberships',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name = 'memberships'
    )
    role = models.CharField(
        max_length=10, choices = Role.choices,
        default=Role.Member)
    joined_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        constraints=[
            models.UniqueConstraint(fields=['user','group'],
            name ='unique_membership' ),
        ]

        def __str__(self):
            return 'f{self.user.username} in{self.group.name} ({self.role}) '
