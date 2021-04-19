import enum

from sqlalchemy.ext.declarative import declarative_base, declared_attr

Base = declarative_base()
from sqlalchemy import (
    TIMESTAMP,
    Column,
    Numeric,
    SmallInteger,
    Integer,
    Enum,
    Float,
    VARCHAR,
)

from sqlalchemy import event, DDL, orm
from geoalchemy2 import Geometry


class HeartRate(Base):
    __tablename__ = "heart_rate"
    time_stamp = Column(TIMESTAMP, nullable=False, primary_key=True)
    heart_rate = Column(Integer)


class HeartRateSummary(Base):
    __tablename__ = "heart_rate_summary"
    time_stamp = Column(TIMESTAMP, nullable=False, primary_key=True)
    resting_heart_rate = Column(Integer)
    out_of_range = Column(Integer)
    fat_burn = Column(Integer)
    cardio = Column(Integer)
    peak = Column(Integer)


# Fitbit improved up on its sleep level tagging on 2019.. So we have different tagging as time passes.
# Stats parsed on April 11 2021
# {'asleep': {'2019', '2017', '2018', '2021', '2016', '2020'}, 'restless': {'2019', '2017', '2018', '2021', '2016', '2020'}, 'awake': {'2019', '2017', '2018', '2021', '2016', '2020'}, 'rem': {'2021', '2020', '2019'}, 'deep': {'2021', '2020', '2019'}, 'wake': {'2021', '2020', '2019'}, 'light': {'2021', '2020', '2019'}, 'unknown': {'2021'}}
class SleepLevel(enum.Enum):
    awake = 0
    restless = 1
    asleep = 2
    unknown = 3


class SleepClassicInfo(Base):
    __tablename__ = "sleep_classic_info"
    time_stamp = Column(TIMESTAMP, nullable=False, primary_key=True)
    sleep_level = Column(Enum(SleepLevel))
    sleep_level_value = Column(Integer, nullable=True)


class SleepStage(enum.Enum):
    wake = 0
    rem = 1
    light = 2
    deep = 3
    unknown = 4


class SleepStagesInfo(Base):
    __tablename__ = "sleep_stages_info"
    time_stamp = Column(TIMESTAMP, nullable=False, primary_key=True)
    sleep_stage = Column(Enum(SleepStage))
    sleep_stage_value = Column(Integer, nullable=True)


class SleepSummary(Base):
    __tablename__ = "sleep_summary"
    time_stamp = Column(TIMESTAMP, nullable=False, primary_key=True)
    num_sleeps = Column(Integer, nullable=True)
    total_sleep_time = Column(Integer, nullable=True)
    total_time_in_bed = Column(Integer, nullable=True)
    main_sleep_start = Column(TIMESTAMP, nullable=True)
    main_sleep_end = Column(TIMESTAMP, nullable=True)
    stage_deep_duration = Column(Integer, nullable=True)
    stage_light_duration = Column(Integer, nullable=True)
    stage_rem_duration = Column(Integer, nullable=True)
    stage_wake_duration = Column(Integer, nullable=True)


class Activity(Base):
    __tablename__ = "activity"
    time_stamp = Column(TIMESTAMP, nullable=False, primary_key=True)
    co_ordinates = Column(
        Geometry(geometry_type="POINT", srid=4326)
    )  # https://postgis.net/workshops/postgis-intro/projection.html
    altitude = Column(Float)
    distance = Column(Float)
    heart_rate = Column(Integer)
    # Not the most optimal but we can improve from here.
    # the activity_id will be stored for each and every instant of Activity for now.
    activity_id = Column(VARCHAR(15))


class ActivityType(enum.Enum):
    # TODO: get the exhaustive list using fitbit API and somehow parse the biiiiig list.
    # https://api.fitbit.com/1/activities.json
    walk = 0
    hike = 1
    workout = 2
    yoga = 3
    run = 4
    weights = 5
    interval_workout = 6
    bike = 7
    sport = 8
    treadmill = 9
    outdoor_bike = 10
    swim = 11
    aerobic_workout = 12
    spinning = 13
    elliptical = 14


class ActivitySummary(Base):
    __tablename__ = "activity_summary"
    time_stamp = Column(TIMESTAMP, nullable=False)
    activity_id = Column(VARCHAR(15), primary_key=True)
    distance = Column(Integer)
    steps = Column(Integer)
    duration = Column(Integer)
    calories = Column(Integer)
    activity_type = Column(Enum(ActivityType))


class DailyActivitySummary(Base):
    __tablename__ = "daily_activity_summary"
    time_stamp = Column(TIMESTAMP, nullable=False, primary_key=True)
    steps = Column(Integer)
    floors = Column(Integer)
    elevation = Column(Integer)
    number_of_activites = Column(Integer)
    sedentary_minutes = Column(Integer)
    lightly_active_minutes = Column(Integer)
    fairly_active_minutes = Column(Integer)
    very_active_minutes = Column(Integer)


@event.listens_for(Activity.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)


@event.listens_for(ActivitySummary.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)


@event.listens_for(DailyActivitySummary.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)


@event.listens_for(HeartRate.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)


@event.listens_for(HeartRateSummary.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    print(dir(DDL))
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)


@event.listens_for(SleepSummary.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    print(dir(DDL))
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)


@event.listens_for(SleepClassicInfo.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    print(dir(DDL))
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)


@event.listens_for(SleepStagesInfo.__table__, "after_create")
def receive_after_create(target, connection, **kw):
    print(dir(DDL))
    DDL(
        f"SELECT create_hypertable('{target}','time_stamp',chunk_time_interval := '1 week'::interval,if_not_exists := true);"
    ).execute(connection)
