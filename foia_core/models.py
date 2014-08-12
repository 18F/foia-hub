import logging
from django.db import models

from django.utils.text import slugify

logger = logging.getLogger(__name__)

# TODO: Confirm statuses
FOIA_STATUS = (
    ('O', 'open'),
    ('S', 'submitted'),
    ('P', 'processing'),
    ('C', 'closed'),
)

# PERSON_TYPE = (
#     ('S', 'contact'),
#     ('L', 'liaison'),
#     ('C', 'chief'),
#     ('B', 'Both'),
# )

#TODO: Add slug to almost everything that could be a page, the
# population that slug


class Agency(models.Model):

    name = models.CharField(max_length=250, unique=True)
    abbreviation = models.CharField(max_length=30, null=True, unique=True)
    description = models.TextField(null=True)
    slug = models.SlugField(unique=True)
    # dept = models.BooleanField()  # This is from csv - possibly removable
    # chief_foia_officer

    def __str__(self):
        return 'Agency: %s' % (self.name,)

    def save(self, *args, **kwargs):
        super(Agency, self).save(*args, **kwargs)
        if not self.slug:
            self.slug = slugify(self.name)[:50]
            super(Agency, self).save(*args, **kwargs)


class Office(models.Model):

    agency = models.ForeignKey(Agency)
    name = models.CharField(max_length=250)
    slug = models.SlugField()

    # phone numbers
    service_center = models.CharField(max_length=250, null=True)
    fax = models.CharField(max_length=50, null=True)

    # electronic comms
    request_form = models.URLField(null=True)
    website = models.URLField(null=True)
    emails = models.CharField(max_length=250, null=True)

    # public contact
    contact = models.TextField(null=True)  # address
    contact_phone = models.CharField(max_length=50, null=True)  # phone

    # Public liaison
    public_liaison = models.TextField(null=True)

    notes = models.TextField(null=True)

    def __str__(self):
        return '%s, %s' % (self.agency.name, self.name)

    class Meta:
        unique_together = (("slug", "agency"),)

    def save(self, *args, **kwargs):
        super(Office, self).save(*args, **kwargs)
        if not self.slug:
            self.slug = slugify(self.name)[:50]
            super(Office, self).save(*args, **kwargs)


# class Person(models.Model):

#     #person_type = models.CharField(max_length=1, choices=PERSON_TYPE)
#     name = models.CharField(max_length=150, null=True)
#     title = models.CharField(max_length=250, null=True)
#     email = models.EmailField(null=True)
#     phone = models.CharField(max_length=50, null=True)

#     street_address = models.CharField(max_length=250, null=True)
#     room_number = models.CharField(max_length=250, null=True)
#     city = models.CharField(max_length=250, null=True)
#     state = models.CharField(max_length=100, null=True)
#     zip_code = models.CharField(max_length=10, null=True)

#     office = models.ForeignKey(Office)

#     def __str__(self):
#         text = None
#         if self.name and self.title:
#             text = '%s, %s' % (self.name, self.title)
#         elif self.name:
#             text = '%s, No title' % self.name
#         elif self.title:
#             text = 'No title, %s' % self.title
#         return 'Person: %s' % text

#     def save(self, *args, **kwargs):
#         """
#         This is to make sure that there is either a name or title.
#         Some titles don't have names and some names don't have titles.
#         """
#         if self.name or self.title:
#             super(Person, self).save(*args, **kwargs)
#         else:
#             logger.warning('%s not saved, because no title or name' % self)


class Requestor(models.Model):

    # TODO: name clarification -- first & last or one field?
    name = models.CharField(max_length=250)
    phone = models.CharField(max_length=10)
    email = models.EmailField()

    #TODO: Add address fields or can we do this without?

    def __str__(self):
        return 'Requestor: %s' % (self.name,)


class FOIARequest(models.Model):

    status = models.CharField(max_length=1, choices=FOIA_STATUS, default='O')
    agency = models.ForeignKey('Requestor')

    request = models.TextField()

    # FEES
    #TODO: If news media, then validate news media email address?
    # How is a member legally defined? Are there other sources that we can
    # validate against
    fee_newsmedia = models.BooleanField(default=False)  # member of media?
    fee_waiver = models.BooleanField(default=False) 	# asking for a waiver?
    fee_limit = models.PositiveIntegerField()  # limit requestor willing to pay

    def __str__(self):
        return 'Request: %s' % (self.pk,)