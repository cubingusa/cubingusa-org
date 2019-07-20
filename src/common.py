import datetime
import calendar
import time
import os
import webapp2

from src import formatters
from src.models.app_settings import AppSettings
from src.models.region import Region
from src.models.state import State
from src.models.user import Roles
from src.models.wca.event import Event
from src.models.wca.export import get_latest_export

class Common(object):
  
  current_date = datetime.datetime.now()
  
  def __init__(self, handler):
    self.uri_for = webapp2.uri_for
    self.uri = handler.request.url
    self.user = handler.user
    self.len = len
    self.formatters = formatters
    self.include_wca_disclaimer = handler.IncludeWcaDisclaimer()
    self.year = datetime.date.today().year

    if self.user:
      last_login_epoch = (self.user.last_login - datetime.datetime(1970,1,1)).total_seconds()
      now_epoch = calendar.timegm(time.gmtime())
      if now_epoch - last_login_epoch < 1:
        self.just_logged_in = True

  def uri_matches(self, path):
    return self.uri.endswith(path)

  def uri_matches_any(self, path_list):
    for text, path in path_list:
      if self.uri_matches(path):
        return True
    return False

  def wca_profile(self, wca_id):
    return 'https://www.worldcubeassociation.org/persons/%s' % wca_id

  def format_date_range(self, start_date, end_date, include_year=True, full_months=False):
    year_chunk = ', %d' % start_date.year if include_year else ''
    month_format = lambda date: date.strftime('%B' if full_months else '%b')
    if start_date == end_date:
      return '%s %d%s' % (month_format(start_date), start_date.day, year_chunk)
    elif start_date.month == end_date.month:
      return '%s %d &ndash; %d%s' % (month_format(start_date), start_date.day,
                                     end_date.day, year_chunk)
    else:
      return '%s %d &ndash; %s %d%s' % (month_format(start_date), start_date.day,
                                        month_format(end_date), end_date.day,
                                        year_chunk)

  def sort_events(self, events):
    return sorted(events, key=lambda evt: evt.get().rank)

  def all_states(self):
    return [state for state in State.query().order(State.name).iter()]

  def regions(self):
    return [r for r in Region.query().order(Region.name).iter()]

  def events(self, include_magic, include_mbo):
    return [e for e in Event.query().order(Event.rank).iter()
            if (include_magic or e.key.id() not in ['magic', 'mmagic']) and
               (include_mbo or e.key.id() != '333mbo')]

  def event(self, event_id):
    return Event.get_by_id(event_id)

  def years(self):
    return reversed(range(2004, datetime.date.today().year + 2))

  def format_date(self, date):
    return '%s %d, %d' % (date.strftime('%B'), date.day, date.year)

  def is_string(self, h):
    return type(h) is str

  def is_none(self, h):
    return h is None

  def get_nav_items(self):
    items = [('Home', '/'),
             ('Competitions', [
                 ('Nationals', '/nationals'),
                 ('Regional Championships', '/regional'),
             ]),
             ('Competitors', [
                 ('State Rankings', '/state_rankings'),
             ]),
             ('Organizers', [
                 ('CubingUSA Supported Competitions', '/supported'),
             ]),
             ('About', [
                 ('About CubingUSA', '/about'),
                 ('Who we are', '/about/who'),
                 ('Donations', '/about/donations'),
                 ('Contact Us', '/about/contact'),
                 ('Logo', '/about/logo'),
                 ('Public Documents', '/about/documents'),
             ]),
            ]
    if self.user and self.user.HasAnyRole(Roles.AdminRoles()):
      admin_list = [('Edit Users', '/admin/edit_users'),
                    ('Edit Championships', '/admin/edit_championships'),
                   ]
      items.append(('Admin', admin_list))
    return items

  def get_right_nav_items(self):
    if self.user:
      return [('My Settings', '/edit'),
              ('Log out', '/logout')]
    else:
      return [('Log in with WCA', '/login')]

  def app_settings(self):
    return AppSettings.Get()

  def get_wca_export(self):
    return get_latest_export().key.id()

  def is_prod(self):
    return not os.environ['SERVER_SOFTWARE'].startswith('Dev')
