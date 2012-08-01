from StringIO import StringIO
import logging
import uuid
from django.core.urlresolvers import reverse
from django.http import HttpResponse
import json
import zipfile
from corehq.apps.app_manager.models import Application
from corehq.apps.reports.models import FormExportSchema
import couchexport
from couchexport.export import get_headers, get_writer, format_tables, create_intermediate_tables
from couchexport.models import FakeSavedExportSchema, Format, SavedExportSchema

# couchexport is a mess. Sorry. Sorry. This is gross, too.

class BulkExport(object):

    @property
    def filename(self):
        return "bulk_export.%s" % Format.from_format(self.format).extension

    @property
    def separator(self):
        return "."

    def create(self, export_tags, export_filter, format=Format.XLS_2007):
        self.export_filter = export_filter
        self.format=format
        self.generate_export_objects(export_tags)

    def generate_export_objects(self, export_tags):
        self.export_objects = []

    def generate_bulk_file(self):
        configs = list()
        schemas = list()
        checkpoints = list()
        file = StringIO()

        for export_object in self.export_objects:
            config, schema, checkpoint = export_object.get_export_components(filter=self.export_filter)
            configs.append(config)
            schemas.append(schema)
            checkpoints.append(checkpoint)

        # generate the headers for the bulk excel file
        headers = []
        for i, schema in enumerate(schemas):
            if not checkpoints[i]:
                continue
            header = self.export_objects[i].parse_headers(get_headers(schema, separator=self.separator))
            headers.extend(header)

        writer = get_writer(self.format)
        writer.open(headers, file)

        # now that the headers are set, lets build the rows
        for i, config in enumerate(configs):
            for doc in config.get_docs():
                if self.export_objects[i].transform:
                    doc = self.export_objects[i].transform(doc)
                table = format_tables(create_intermediate_tables(doc, schemas[i]),
                                    include_headers=False, separator=self.separator)
                table = self.export_objects[i].parse_tables(table)
                writer.write(table)

        writer.close()
        return file

    def generate_table_headers(self, schemas, checkpoints):
        return []

class CustomBulkExport(BulkExport):
    domain = None

    @property
    def filename(self):
        return "%s_custom_bulk_export.%s" % (self.domain, Format.from_format(self.format).extension)

    def generate_export_objects(self, export_tags):
        self.export_objects = []
        for tag in export_tags:
            export_id = tag.get('export_id', None)
            export_type = tag.get('type', 'form')
            sheet_name = tag.get('sheet_name', 'Untitled')

            if export_type == 'form':
                ExportSchemaClass = FormExportSchema
            else:
                ExportSchemaClass = SavedExportSchema
            if export_id:
                export_object = ExportSchemaClass.get(export_id)
                export_object.sheet_name = sheet_name
                self.export_objects.append(export_object)

    def generate_table_headers(self, schemas, checkpoints):
        headers = []
        for export_object in self.export_objects:
            if export_object.parse_headers:
                headers.extend(export_object.parse_headers(export_object.get_table_headers()))
            else:
                logging.error("Not able to parse a header during custom bulk export.")
        return headers

class ApplicationBulkExport(BulkExport):
    export_id = None

    @property
    def filename(self):
        file_ext = Format.from_format(self.format).extension
        filename = "%s.%s" % (self.export_id, file_ext)
        try:
            app = Application.get(self.export_id)
            if app:
                filename = "%s-%s.%s" %(app.name, app.get_id, file_ext)
        except Exception:
            pass
        return filename

    @property
    def separator(self):
        return "|"

    def generate_table_headers(self, schemas, checkpoints):
        headers = []
        for i, schema in enumerate(schemas):
            if not checkpoints[i]:
                continue
            header = self.export_objects[i].parse_headers(get_headers(schema, separator=self.separator))
            headers.extend(header)
        return headers

    def generate_export_objects(self, export_tags):
        self.export_objects = []
        for schema_index in export_tags:
            self.export_objects.append(FakeSavedExportSchema(index=schema_index))


class BulkExportHelper(object):

    @property
    def zip_export(self):
        return True

    def prepare_export(self, export_tags, export_filter, domain=None):
        self.domain = domain
        self.generate_bulk_files(export_tags, export_filter)

        download_id = uuid.uuid4().hex
        couchexport.tasks.bulk_export_async.delay(
            self,
            download_id,
            domain=self.domain
        )
        return HttpResponse(json.dumps(dict(
            download_id=download_id,
            download_url=reverse('ajax_job_poll', kwargs={'download_id': download_id}))
        ))

    def generate_bulk_files(self, export_tags, export_filter):
        self.bulk_files = []

    @property
    def get_id(self):
        return uuid.uuid4().hex


class ApplicationBulkExportHelper(BulkExportHelper):

    def generate_bulk_files(self, export_tags, export_filter):
        self.bulk_files = []
        for appid, indices in export_tags.items():
            app_bulk_export = ApplicationBulkExport()
            app_bulk_export.create(indices, export_filter)
            app_bulk_export.export_id = appid
            self.bulk_files.append(app_bulk_export)

class CustomBulkExportHelper(BulkExportHelper):

    @property
    def zip_export(self):
        return False

    def generate_bulk_files(self, export_tags, export_filter):
        bulk_export = CustomBulkExport()
        bulk_export.create(export_tags, export_filter)
        bulk_export.domain = self.domain
        self.bulk_files = [bulk_export]