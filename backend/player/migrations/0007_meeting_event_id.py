# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-06 16:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('player', '0006_remove_player_events'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='event_id',
            field=models.IntegerField(blank=None, default=None, null=None),
        ),
    ]
