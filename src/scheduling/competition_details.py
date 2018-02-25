import collections
import json

from google.appengine.ext import ndb

from src.models.scheduling.round import ScheduleRound
from src.models.scheduling.schedule import Schedule
from src.models.scheduling.stage import ScheduleStage
from src.models.scheduling.time_block import ScheduleTimeBlock
from src.models.wca.rank import RankAverage
from src.models.wca.rank import RankSingle


class GroupedTimeBlock(object):
  def __init__(self, t, r, s):
    self._time_blocks = [t]
    self._start_time = t.GetStartTime()
    self._end_time = t.GetEndTime()
    self._stage_keys = set([t.stage])
    self._stages = [s]
    self._round = r

  def AddTimeBlock(self, t, s):
    self._time_blocks.append(t)
    self._end_time = max(self._end_time, t.GetEndTime())
    if s.key not in self._stage_keys:
      self._stage_keys.add(s.key)
      self._stages.append(s)

  def GetStartTime(self):
    return self._start_time

  def GetEndTime(self):
    return self._end_time

  def FormatTimes(self):
    return '%s %s - %s' % (
        self._start_time.strftime('%A'),
        self._start_time.strftime('%I:%M %p').lstrip('0'),
        self._end_time.strftime('%I:%M %p').lstrip('0'))

  def GetRound(self):
    return self._round

  def GetStages(self):
    return sorted(self._stages, key=lambda s: s.number)


class RoundDetails(object):
  def __init__(self, r):
    self._r = r
    self._grouped_time_blocks = []

  def GetRound(self):
    return self._r

  def AddTimeBlock(self, t, s):
    if (self._grouped_time_blocks and
        t.GetStartTime() < self._grouped_time_blocks[-1].GetEndTime()):
      self._grouped_time_blocks[-1].AddTimeBlock(t, s)
    else:
      self._grouped_time_blocks.append(GroupedTimeBlock(t, self._r, s))

  def GetGroupedTimeBlocks(self):
    return self._grouped_time_blocks
    

class EventDetails(object):
  def __init__(self):
    self._event = None
    self._rounds = {}
    self._qualifying_time = None
    self._qualifying_time_is_average = False
    self._is_qualified = False

  def AddRound(self, r):
    self._rounds[r.number] = RoundDetails(r)

  def AddTimeBlock(self, t, r, s):
    self._rounds[r.number].AddTimeBlock(t, s)

  def GetEvent(self):
    return self._event

  def SetEvent(self, event):
    self._event = event

  def GetRounds(self):
    return self._rounds.values()

  def GetQualifyingTime(self):
    return self._qualifying_time

  def QualifyingTimeIsAverage(self):
    return self._qualifying_time_is_average

  def IsQualified(self):
    return self._is_qualified

  def SetQualifyingTime(self, time, is_average, is_qualified):
    self._qualifying_time = time
    self._qualifying_time_is_average = is_average
    self._is_qualified = is_qualified


class CompetitionDetails(object):
  def __init__(self, user, competition, schedule=None):
    self.user = user
    self.competition = competition
    if schedule:
      self.schedule = schedule
    else:
      self.schedule = Schedule.query(ndb.AND(Schedule.competition == competition.key,
                                             Schedule.is_live == True)).get()
    if not self.schedule:
      return

    self.event_details = {}
    self.event_keys = []
    self.stage_ids = set()

    rounds_by_id = {}
    stages_by_id = {
        stage.key.id() : stage
        for stage in ScheduleStage.query(ScheduleStage.schedule == self.schedule.key).iter()
    }

    for r in ScheduleRound.query(ScheduleRound.schedule == self.schedule.key).iter():
      if r.event.id() not in self.event_details:
        self.event_details[r.event.id()] = EventDetails()
        self.event_keys.append(r.event)
      self.event_details[r.event.id()].AddRound(r)
      rounds_by_id[r.key.id()] = r

    # Load the events from the datastore.
    events_by_id = {e.key.id() : e
                    for e in ndb.get_multi(self.event_keys)}
    for event_id, event in events_by_id.iteritems():
      self.event_details[event_id].SetEvent(event)

    for t in (ScheduleTimeBlock.query(ndb.AND(ScheduleTimeBlock.schedule == self.schedule.key,
                                              ScheduleTimeBlock.staff_only == False))
                               .order(ScheduleTimeBlock.start_time)
                               .iter()):
      r = rounds_by_id[t.round.id()]
      self.event_details[r.event.id()].AddTimeBlock(t, r, stages_by_id[t.stage.id()])
      self.stage_ids.add(t.stage.id())
    if user and user.wca_person:
      self.ranks_single = {
          r.event.id() : r for r in
          RankSingle.query(RankSingle.person == user.wca_person).iter()}
      self.ranks_average = {
          r.event.id() : r for r in
          RankAverage.query(RankAverage.person == user.wca_person).iter()}
    else:
      self.ranks_single = {}
      self.ranks_average = {}

  def SetQualifyingTime(self, event_id, time, is_average):
    ranks_dict = self.ranks_average if is_average else self.ranks_single
    is_qualified = event_id in ranks_dict and ranks_dict[event_id].best <= time
    self.event_details[event_id].SetQualifyingTime(time, is_average, is_qualified)

  def GetEvents(self):
    return sorted(self.event_details.values(), key=lambda e: e.GetEvent().rank)

  def GetWcaEvents(self):
    return [e.GetEvent() for e in self.GetEvents()]

  def HasQualifyingTimes(self):
    for e in self.event_details.itervalues():
      if e.GetQualifyingTime():
        return True
    return False

  def HasMultipleRoundEvents(self):
    for e in self.event_details.itervalues():
      if len(e.GetRounds()) > 1:
        return True
    return False

  def HasCutoffs(self):
    for e in self.event_details.itervalues():
      for r in e.GetRounds():
        if r.GetRound().cutoff:
          return True
    return False

  def TimeBlocksByDay(self):
    time_blocks_dict = collections.defaultdict(list)
    for e in self.event_details.itervalues():
      for r in e.GetRounds():
        for t in r.GetGroupedTimeBlocks():
          time_blocks_dict[t.GetStartTime().date()].append(t)
    for time_blocks in time_blocks_dict.itervalues():
      time_blocks.sort(key=lambda t: t.GetStartTime())
    # Sort by day.
    return sorted(time_blocks_dict.items(), key=lambda i: i[0])

  def HasMultipleStages(self):
    return len(self.stage_ids) > 1
