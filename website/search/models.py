from django.db import models


class JobInfo(models.Model):
    title = models.CharField(max_length=200)
    info = models.TextField()

