from google.appengine.ext import ndb

from src import common
from src.handlers.base import BaseHandler
from src.jinja import JINJA_ENVIRONMENT
from src.models.champion import Champion
from src.models.championship import Championship
from src.models.region import Region
from src.models.state import State
from src.models.wca.event import Event

# An async handler to return a table of the champions in a particular year.
class ChampionsByYearHandler(BaseHandler):
  def get(self, event_id, championship_type, championship_region):
    template = JINJA_ENVIRONMENT.get_template('champions_by_year.html')
    all_champions = []
    if championship_type == 'national':
      all_champions = [c for c in Champion.query(Champion.national_champion == True).iter()]
    elif championship_type == 'regional':
      all_champions = [c for c in Champion.query(Champion.region ==
                                                 ndb.Key(Region, championship_region)).iter()]
    elif championship_type == 'state':
      all_champions = [c for c in Champion.query(Champion.state ==
                                                 ndb.Key(State, championship_region)).iter()]
    all_champions = sorted([c for c in all_champions
                            if c.event == ndb.Key(Event, str(event_id))],
                           key = lambda c: c.championship.id(), reverse=True)
    championship_keys = [champion.championship for champion in all_champions]
    championships = ndb.get_multi(championship_keys)
    competition_keys = [championship.competition
                        for championship in championships
                        if championship]
    winner_keys = [winner
                   for champion in all_champions
                   for winner in champion.champions]
    entities_by_id = {e.key.id() : e
                      for e in ndb.get_multi(competition_keys + winner_keys)
                      if e}

    # Pass the template a list of pairs of competitions and winners, to save
    # datastore RPCs.
    competitions_and_winners = []
    for champion, championship in zip(all_champions, championships):
      competitions_and_winners.append((
          entities_by_id[championship.competition.id()],
          [entities_by_id[winner_key.id()] for winner_key in champion.champions]))
    self.response.write(template.render({
        'c': common.Common(self),
        'competitions_and_winners': competitions_and_winners,
    }))
