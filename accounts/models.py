from django.db import models
from django.conf import settings
# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name = 'profile',
    )
    upi_id = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=10, blank=True)
    avatar = models.ImageField(upload_to='avatar/',blank =True, null=True)

    def __str__(self):
        return f'{self.user.username} profile'