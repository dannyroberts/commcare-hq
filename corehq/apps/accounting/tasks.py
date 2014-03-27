from urllib import urlencode
from celery.schedules import crontab
from celery.task import task, periodic_task
from celery.utils.log import get_task_logger
import datetime
from django.conf import settings
from django.http import HttpRequest, QueryDict
from corehq import Domain
from corehq.apps.accounting import utils
from corehq.apps.accounting.exceptions import InvoiceError, CreditLineError
from corehq.apps.accounting.invoicing import DomainInvoiceFactory

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import has_subscription_already_ended
from corehq.apps.users.models import FakeUser
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.django.email import send_HTML_email

logger = get_task_logger(__name__)


@periodic_task(run_every=crontab(minute=0, hour=0))
def activate_subscriptions(based_on_date=None):
    """
    Activates all subscriptions starting today (or, for testing, based on the date specified)
    """
    starting_date = based_on_date or datetime.date.today()
    starting_subscriptions = Subscription.objects.filter(date_start=starting_date)
    for subscription in starting_subscriptions:
        if not has_subscription_already_ended(subscription):
            subscription.is_active = True
            subscription.save()


@periodic_task(run_every=crontab(minute=0, hour=0))
def deactivate_subscriptions(based_on_date=None):
    """
    Deactivates all subscriptions ending yesterday (or, for testing, based on the date specified)
    """
    ending_date = based_on_date or datetime.date.today()
    ending_subscriptions = Subscription.objects.filter(date_end=ending_date)
    for subscription in ending_subscriptions:
        subscription.is_active = False
        subscription.save()


@task
def generate_invoices(based_on_date=None):
    """
    Generates all invoices for the past month.
    """
    today = based_on_date or datetime.date.today()
    invoice_start, invoice_end = utils.get_previous_month_date_range(today)

    all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
    for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
        domain = Domain.wrap(domain_doc)
        try:
            invoice_factory = DomainInvoiceFactory(invoice_start, invoice_end, domain)
            invoice_factory.create_invoices()
        except CreditLineError as e:
            logger.error("There was an error utilizing credits for "
                         "domain %s: %s" % (domain.name, e))
        except InvoiceError as e:
            logger.error("Could not create invoice for domain %s: %s" % (
                domain.name, e
            ))


@task
def send_bookkeeper_email(month=None, year=None, emails=None):
    today = datetime.date.today()
    month = month or today.month
    year = year or today.year

    from corehq.apps.accounting.interface import InvoiceInterface
    request = HttpRequest()
    params = urlencode((
        ('report_filter_statement_period_month', month),
        ('report_filter_statement_period_year', year),
    ))
    request.GET = QueryDict(params)
    request.couch_user = FakeUser(
        domain="hqadmin",
        username="admin@dimagi.com",
    )
    invoice = InvoiceInterface(request)
    email_content = invoice.email_response

    emails = emails or settings.BOOKKEEPER_CONTACT_EMAILS
    for email in emails:
        send_HTML_email(
            "Invoices for %s" % datetime.date(year, month, 1).strftime("%B %Y"),
            email,
            email_content,
            email_from=settings.DEFAULT_FROM_EMAIL
        )


