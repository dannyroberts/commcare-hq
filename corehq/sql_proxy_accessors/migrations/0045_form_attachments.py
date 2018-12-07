# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-11-17 20:58
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration, SQL

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0044_blobmeta_form_attachments'),
    ]

    operations = [
        migrator.get_migration(
            SQL("DROP FUNCTION IF EXISTS get_form_attachment_by_name(TEXT, TEXT)"),
            "get_form_attachment_by_name.sql",
        ),
        migrator.get_migration(
            SQL("DROP FUNCTION IF EXISTS get_form_attachments(TEXT)"),
            "get_form_attachments.sql",
        ),
        migrator.get_migration(
            SQL("DROP FUNCTION IF EXISTS get_multiple_forms_attachments(TEXT[])"),
            "get_multiple_forms_attachments.sql",
        ),
    ]