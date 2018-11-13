# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-11-07 16:51
from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations, models
from corehq.sql_db.operations import RawSQLMigration
from custom.icds_reports.utils.migrations import get_view_migrations


migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0073_ccsrecordmonthly_closed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='awwincentivereport',
            name='expected_visits',
            field=models.DecimalField(decimal_places=2, max_digits=64, null=True),
        ),
        migrator.get_migration('update_tables30.sql'),
    ]
    operations.extend(get_view_migrations())