import datetime
import logging

from google.appengine.ext import ndb

from src import common
from src import timezones
from src.handlers.base import BaseHandler
from src.jinja import JINJA_ENVIRONMENT
from src.models.championship import Championship
from src.models.eligibility import RegionalChampionshipEligibility
from src.models.eligibility import StateChampionshipEligibility
from src.models.scheduling.competition import ScheduleCompetition
from src.models.scheduling.person import SchedulePerson
from src.models.state import State
from src.models.user import User
from src.models.user import UserLocationUpdate
from src.models.wca.event import Event
from src.models.wca.rank import RankAverage
from src.models.wca.rank import RankSingle


class ChampionshipPsychHandler(BaseHandler):
  def get(self, region_or_state, year):
    # We should call RegionalsId or StateChampionshipId here, but we don't know
    # yet what kind of championship this is.
    championship_id = '%s_%s' % (region_or_state, year)

    championship = Championship.get_by_id(championship_id)
    if not championship:
      template = JINJA_ENVIRONMENT.get_template('error.html')
      self.response.write(template.render({
          'c': common.Common(self),
          'error': 'Sorry!  We don\'t know about that championship yet.',
      }))
      return

    event_keys = set()
    # This query is ugly because we have two separate representations of
    # competitions in the datastore: ScheduleCompetition (competitions using the
    # scheduling system) and Competition (competitions from the WCA DB export).
    for competitor in SchedulePerson.query(
                          SchedulePerson.competition ==
                          ndb.Key(ScheduleCompetition, championship.competition.id())).iter():
      for event in competitor.registered_events:
        event_keys.add(event)
    events = sorted(ndb.get_multi(event_keys), key=lambda e: e.rank)
    deadline = timezones.ToLocalizedTime(championship.residency_deadline,
                                         championship.residency_timezone)

    states = ndb.get_multi(championship.GetEligibleStateKeys())
    if championship.region:
      championship_title = championship.region.get().championship_name
      state_names = [state.name for state in State.query(State.region == championship.region).iter()]
      state_list = ' and '.join([', '.join(state_names[:-1]), state_names[-1]])
    elif championship.state:
      championship_title = championship.state.get().name + ' State'
      state_list = championship.state.get().name

    template = JINJA_ENVIRONMENT.get_template('championship_psych.html')
    self.response.write(template.render({
        'c': common.Common(self),
        'championship': championship,
        'competition': championship.competition.get(),
        'championship_title': championship_title,
        'championship_id': championship_id,
        'state_list': state_list,
        'events': events,
        'deadline': deadline,
        'deadline_passed': championship.residency_deadline < datetime.datetime.now(),
    }))

  def IncludeWcaDisclaimer(self):
    return True


class CompetitorInfo(object):
  def __init__(self, competitor):
    self.competitor = competitor
    self.user_id = competitor.user.id()
    if competitor.wca_person:
      self.wca_id = competitor.wca_person.id()
    self.best = 999999999
    self.state_key = None
    self.eligibility = None


class ChampionshipPsychAsyncHandler(BaseHandler):
  def get(self, championship_id, event_id):
    logging.info('start')
    championship = Championship.get_by_id(championship_id)
    if not championship:
      self.response.status = 404
      return
    competitors = SchedulePerson.query(ndb.AND(
                      SchedulePerson.competition == ndb.Key(ScheduleCompetition,
                                                            championship.competition.id()),
                      SchedulePerson.registered_events == ndb.Key(Event, event_id))).fetch()

    competitors_by_wca_id = {}
    competitors_by_user_id = {}
    wca_person_keys = []
    user_keys = []
    for competitor in competitors:
      competitor_info = CompetitorInfo(competitor)
      competitors_by_user_id[competitor_info.user_id] = competitor_info
      user_keys.append(competitor.user)
      if competitor.wca_person:
        competitors_by_wca_id[competitor_info.wca_id] = competitor_info
        wca_person_keys.append(competitor.wca_person)
    logging.info('got competitors')

    wca_people = ndb.get_multi(wca_person_keys)

    residency_deadline = championship.residency_deadline or datetime.datetime.now()
    # First look up residency for accounts keyed by person WCA id.
    user_wca_id_keys = [ndb.Key(User, wca_person.id()) for wca_person in wca_person_keys]
    for update in (UserLocationUpdate.query(
                        ndb.AND(UserLocationUpdate.user.IN(user_wca_id_keys),
                                UserLocationUpdate.update_time < residency_deadline))
                       .order(UserLocationUpdate.update_time)
                       .iter()):
      competitors_by_wca_id[update.user.id()].state_key = update.state

    # Next look up residency for accounts keyed by user id.
    # We do this second to override accounts keyed by WCA ID, since user ID
    # updates are newer.
    for update in (UserLocationUpdate.query(
                        ndb.AND(UserLocationUpdate.user.IN(user_keys),
                                UserLocationUpdate.update_time < residency_deadline))
                       .order(UserLocationUpdate.update_time)
                       .iter()):
      competitors_by_user_id[update.user.id()].state_key = update.state
    logging.info('got locations')

    # Next, look up eligibilities that have already been used for this year.
    eligibility_class = (RegionalChampionshipEligibility if championship.region
                         else StateChampionshipEligibility)
    for eligibility in eligibility_class.query(ndb.AND(
                           eligibility_class.user.IN(user_wca_id_keys + user_keys),
                           eligibility_class.year == championship.year)).iter():
      if eligibility.championship != championship.key:
        if eligibility.user.id() in competitors_by_wca_id:
          competitors_by_wca_id[eligibility.user.id()].eligibility = eligibility
        if eligibility.user.id() in competitors_by_user_id:
          competitors_by_user_id[eligibility.user.id()].eligibility = eligibility
    logging.info('got eligibilities')

    # Finally look up personal bests.
    rank_class = RankSingle if 'bf' in event_id else RankAverage
    for rank in rank_class.query(ndb.AND(rank_class.event == ndb.Key(Event, event_id),
                                         rank_class.person.IN(wca_person_keys))).iter():
      competitors_by_wca_id[rank.person.id()].best = rank.best
    logging.info('got ranks')

    # Now break competitors into those who are eligible and those who aren't.
    eligible_competitors = []
    ineligible_competitors = []
    eligible_state_keys = championship.GetEligibleStateKeys()
    for competitor in competitors_by_user_id.itervalues():
      if (not competitor.eligibility and
          competitor.state_key in eligible_state_keys):
        eligible_competitors.append(competitor)
      else:
        ineligible_competitors.append(competitor)

    eligible_competitors.sort(key=lambda c: c.best)
    ineligible_competitors.sort(key=lambda c: c.best)
    logging.info('sorted')

    template = JINJA_ENVIRONMENT.get_template('championship_psych_table.html')
    self.response.write(template.render({
        'c': common.Common(self),
        'event': Event.get_by_id(event_id),
        'eligible_competitors': eligible_competitors,
        'ineligible_competitors': ineligible_competitors,
        'is_average': 'bf' not in event_id,
    }))
    logging.info('done')
