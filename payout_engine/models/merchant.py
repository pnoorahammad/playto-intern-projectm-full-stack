from django.db import models

class MerchantQuerySet(models.QuerySet):
    def get_for_update(self, pk):
        """Standardized interface for acquiring a row-level lock on a merchant."""
        return self.select_for_update().get(pk=pk)

class Merchant(models.Model):
    name = models.CharField(max_length=255)
    
    objects = MerchantQuerySet.as_manager()

    class Meta:
        db_table = 'merchant'
