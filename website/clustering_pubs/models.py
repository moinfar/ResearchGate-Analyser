from django.db import models


class DocClusteringInfo(models.Model):
    k = models.IntegerField(verbose_name='K')
    iter = models.IntegerField(verbose_name='Iteration Number')
    cost = models.FloatField(verbose_name='Cost')
    status = models.TextField(verbose_name='Status')
    index_name = models.TextField(verbose_name='Index Name', unique=True, primary_key=True)
    doc_type = models.TextField(verbose_name='Document Type')
