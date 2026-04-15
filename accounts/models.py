from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
# Add this import
from cloudinary.models import CloudinaryField

class BankUser(AbstractUser):
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    # Change ImageField to CloudinaryField
    face_encoding_sample = CloudinaryField('image', folder='face_samples', null=True, blank=True)

    def has_active_license(self):
        return self.licenses.filter(expiry_date__gt=timezone.now(), is_active=True).exists()

class License(models.Model):
    user = models.ForeignKey(BankUser, on_delete=models.CASCADE, related_name='licenses')
    license_key = models.CharField(max_length=100, unique=True)
    expiry_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"License for {self.user.username} (Expires: {self.expiry_date})"