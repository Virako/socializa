# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-30 08:34
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0008_auto_20170114_2009'),
    ]

    operations = [
        migrations.AlterField(
            model_name='membership',
            name='status',
            field=models.CharField(choices=[('registered', 'registered'), ('paying', 'paying'), ('payed', 'payed'), ('cancelled', 'cancelled'), ('solved', 'solved')], default='registered', max_length=16),
        ),
    ]
