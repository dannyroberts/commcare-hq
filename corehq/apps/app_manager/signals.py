from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch.dispatcher import Signal

from corehq.apps.callcenter.app_parser import get_call_center_config_from_app
from corehq.apps.domain.models import Domain
from dimagi.utils.logging import notify_exception


def create_app_structure_repeat_records(sender, application, **kwargs):
    from corehq.motech.repeaters.models import AppStructureRepeater
    domain = application.domain
    if domain:
        repeaters = AppStructureRepeater.by_domain(domain)
        for repeater in repeaters:
            repeater.register(application)


def update_callcenter_config(sender, application, **kwargs):
    if not application.copy_of:
        return

    try:
        domain = Domain.get_by_name(application.domain)
        cc_config = domain.call_center_config
        if not cc_config or not (cc_config.fixtures_are_active() and cc_config.config_is_valid()):
            return

        app_config = get_call_center_config_from_app(application)
        save = cc_config.update_from_app_config(app_config)
        if save:
            cc_config.save()
    except Exception:
        notify_exception(None, "Error updating CallCenter config for app build")


app_post_save = Signal(providing_args=['application'])

app_post_save.connect(create_app_structure_repeat_records)
app_post_save.connect(update_callcenter_config)

app_post_release = Signal(providing_args=['application'])
