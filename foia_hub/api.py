import datetime

from django.db import transaction
from django.conf.urls import patterns, url
from django.shortcuts import get_object_or_404

from restless.dj import DjangoResource
from restless.resources import skip_prepare
from restless.preparers import FieldsPreparer
from restless.exceptions import BadRequest

from foia_hub.models import Agency, Office, Requester, FOIARequest

from django.db import connection

import re
import string


def sanitize_search_term(term):
    # Replace all puncuation with spaces.
    allowed_punctuation = set(['&', '|', '"', "'"])
    all_punctuation = set(string.punctuation)
    punctuation = "".join(all_punctuation - allowed_punctuation)
    term = re.sub(r"[{}]+".format(re.escape(punctuation)), " ", term)

    # Substitute all double quotes to single quotes.
    term = term.replace('"', "'")
    term = re.sub(r"[']+", "'", term)

    # Create regex to find strings within quotes.
    quoted_strings_re = re.compile(r"('[^']*')")
    space_between_words_re = re.compile(r'([^ &|])[ ]+([^ &|])')
    spaces_surrounding_letter_re = re.compile(r'[ ]+([^ &|])[ ]+')
    multiple_operator_re = re.compile(r"[ &]+(&|\|)[ &]+")

    tokens = quoted_strings_re.split(term)
    processed_tokens = []
    for token in tokens:
        # Remove all surrounding whitespace.
        token = token.strip()

        if token in ['', "'"]:
            continue

        if token[0] != "'":
            # Surround single letters with &'s
            token = spaces_surrounding_letter_re.sub(r' & \1 & ', token)

            # Specify '&' between words that have neither | or & specified.
            token = space_between_words_re.sub(r'\1 & \2', token)

            # Add a prefix wildcard to every search term.
            token = re.sub(r'([^ &|]+)', r'\1:*', token)

        processed_tokens.append(token)

    term = " & ".join(processed_tokens)

    # Replace ampersands or pipes surrounded by ampersands.
    term = multiple_operator_re.sub(r" \1 ", term)

    # Escape single quotes
    return term.replace("'", "''")


def contact_preparer():
    return FieldsPreparer(fields={
        'name': 'name',
        'person_name': 'person_name',
        'emails': 'emails',
        'phone': 'phone',
        'toll_free_phone': 'toll_free_phone',
        'fax': 'fax',

        'public_liaison_name': 'public_liaison_name',
        'public_liaison_email': 'public_liaison_email',
        'public_liaison_phone': 'public_liaison_phone',

        'request_form_url': 'request_form_url',
        'office_url': 'office_url',

        'address_lines': 'address_lines',
        'street': 'street',
        'city': 'city',
        'state': 'state',
        'zip_code': 'zip_code',
    })


def agency_preparer():
    return FieldsPreparer(fields={
        'name': 'name',
        'description': 'description',
        'abbreviation': 'abbreviation',
        'slug': 'slug',
        'keywords': 'keywords',
        'common_requests': 'common_requests'
    })


def office_preparer():
    preparer = FieldsPreparer(fields={
        'id': 'id',
        'name': 'name',
        'slug': 'slug',
    })
    return preparer


def get_latest_stats(stat_type, agency=None, office=None):
    """Gets the latest median processing time stats for an agency/office.
    """

    if agency and not office:
        stats = agency.stats_set \
            .filter(office=None, stat_type=stat_type) \
            .order_by('-year').first()
    if office and not agency:
        stats = office.stats_set \
            .filter(stat_type=stat_type) \
            .order_by('-year').first()

    if stats:
        return stats.median
    else:
        return None


def foia_libraries_preparer(contactable):
    data = {}
    libraries = []
    for rru in contactable.reading_room_urls.all():
        libraries.append({'link_text': rru.link_text, 'url': rru.url})
    data['foia_libraries'] = libraries
    return data


class AgencyResource(DjangoResource):
    """ The resource that represents the endpoint for an Agency """

    preparer = agency_preparer()

    def __init__(self, *args, **kwargs):
        super(AgencyResource, self).__init__(*args, **kwargs)
        self.office_preparer = office_preparer()
        self.contact_preparer = contact_preparer()

    def prepare_agency_contact(self, agency):
        offices = []
        components = agency.get_all_components()
        for o in components:
            offices.append(self.office_preparer.prepare(o))

        simple = get_latest_stats(stat_type="S", agency=agency)
        comp = get_latest_stats(stat_type="C", agency=agency)

        data = {
            'offices': offices,
            'is_a': 'agency',
            'agency_slug': agency.slug,
            'agency_name': agency.name,
            'no_records_about': agency.no_records_about,
            'simple_processing_time': simple,
            'complex_processing_time': comp,
        }

        # some agencies have parents (e.g. FBI->DOJ)
        if agency.parent:
            data['parent'] = AgencyResource.preparer.prepare(agency.parent)

        data.update(foia_libraries_preparer(agency))
        data.update(AgencyResource.preparer.prepare(agency))
        data.update(self.contact_preparer.prepare(agency))
        return data

    def list(self, q=None):
        """ This lists all Agency objects, optionally filtered by a given
        query parameter. It doesn't provide every field for every object,
        instead limiting the output to useful fields. To see the detail for
        each object, use the detail endpoint. """

        # Use request 'query' parameter if it exists
        if self.request and 'query' in self.request.GET:
            q = self.request.GET.get('query', None)

        if q:
            search_term = sanitize_search_term(q)

            cursor = connection.cursor()
            cursor.execute(
                """
SELECT * FROM foia_hub_agency
WHERE id IN (
    SELECT id
    FROM (
        SELECT * ,
            setweight(to_tsvector('english', name), 'A') ||
            setweight(to_tsvector('english', description), 'B') as score
        FROM foia_hub_agency
        ) as results
    WHERE results.score @@ to_tsquery('english', %s)
    ORDER BY ts_rank(results.score, to_tsquery('english', %s)) DESC);
                """,
                [search_term, search_term])
            agencies = cursor.fetchall()
            print(agencies)
        else:
            agencies = Agency.objects.all()

        return agencies #.order_by('name')

    @skip_prepare
    def detail(self, slug):
        """ A detailed return of an Agency objects. """
        agency = get_object_or_404(Agency, slug=slug)
        response = self.prepare_agency_contact(agency)
        return response

    @classmethod
    def urls(cls, name_prefix=None):
        urlpatterns = super(
            AgencyResource, cls).urls(name_prefix=name_prefix)
        return patterns(
            '',
            url(
                r'^(?P<slug>[\w-]+)/$',
                cls.as_view('detail'),
                name=cls.build_url_name('detail', name_prefix)),
        ) + urlpatterns


class OfficeResource(DjangoResource):
    """ The resource that represents the endpoint for an Office. """

    def __init__(self, *args, **kwargs):
        super(OfficeResource, self).__init__(*args, **kwargs)
        self.agency_preparer = agency_preparer()
        self.office_preparer = office_preparer()
        self.contact_preparer = contact_preparer()

    @skip_prepare
    def detail(self, slug):
        """ A detailed return of an Office object. """
        office = get_object_or_404(Office, slug=slug)
        response = self.prepare_office_contact(office)
        return response

    def prepare_office_contact(self, office):
        office_data = self.office_preparer.prepare(office)

        simple = get_latest_stats(stat_type="S", office=office)
        comp = get_latest_stats(stat_type="C", office=office)

        data = {
            'agency_name': office.agency.name,
            'agency_slug': office.agency.slug,
            'office_slug': office.office_slug,
            'agency_description': office.agency.description,
            'is_a': 'office',
            'simple_processing_time': simple,
            'complex_processing_time': comp,
        }

        data.update(foia_libraries_preparer(office))
        data.update(office_data)
        data.update(self.contact_preparer.prepare(office))
        return data

    @classmethod
    def urls(cls, name_prefix=None):
        urlpatterns = super(
            OfficeResource, cls).urls(name_prefix=name_prefix)
        return patterns(
            '',
            url(
                r'^(?P<slug>[\w-]+)/$',
                cls.as_view('detail'),
                name=cls.build_url_name('detail', name_prefix)),
        ) + urlpatterns


class FOIARequestResource(DjangoResource):

    preparer = FieldsPreparer(fields={
        'status': 'status',
        'tracking_id': 'pk',
    })

    def _convert_date(self, date):
        return datetime.datetime.strptime(date, '%B %d, %Y')

    def check_submittable(self, email_list):
        """ If there is no email for this agency or office, we can not accept a
        FOIA request. """

        if len(email_list) == 0:
            raise BadRequest(
                msg="Agency or Office has no email address for submission")

    # POST /
    def create(self):

        foia = None
        with transaction.atomic():

            # Is this request to an Agency, or an Office?
            if self.data.get('office') and self.data.get('agency'):
                office = Office.objects.get(
                    agency__slug=self.data['agency'],
                    office_slug=self.data['office'],
                )
                agency = None
                emails = office.emails
            elif self.data.get('agency'):
                agency = Agency.objects.get(
                    slug=self.data['agency']
                )
                office = None
                emails = agency.emails

            # Not sure yet what this actually returns.
            # restless docs could be better on this point.
            else:
                raise Exception("No agency or office given.")

            self.check_submittable(emails)

            requester = Requester.objects.create(
                first_name=self.data['first_name'],
                last_name=self.data['last_name'],
                email=self.data['email']
            )

            if self.data.get("documents_start"):
                start = self._convert_date(self.data['documents_start'])
            else:
                start = None

            if self.data.get("documents_end"):
                end = self._convert_date(self.data['documents_end'])
            else:
                end = None

            foia = FOIARequest.objects.create(
                status='O',
                requester=requester,
                office=office,
                agency=agency,
                emails=emails,
                date_start=start,
                date_end=end,
                request_body=self.data['body'],
            )

        return foia

    # GET /
    def list(self):
        return FOIARequest.objects.all()

    # Open everything wide!
    # DANGEROUS, DO NOT DO IN PRODUCTION.
    # more info here:
    # https://github.com/toastdriven/restless/blob/master/docs/tutorial.rst
    def is_authenticated(self):
        return True
