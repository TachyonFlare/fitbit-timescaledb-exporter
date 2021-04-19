import sys
import json
from os import listdir
from os.path import join, isdir, isfile, sep
import xml.etree.ElementTree as ET

import arrow
from sqlalchemy import create_engine, func
from sqlalchemy.orm import relationship, backref, sessionmaker
from models import (
    Base,
    HeartRate,
    HeartRateSummary,
    SleepSummary,
    SleepStagesInfo,
    SleepClassicInfo,
    SleepLevel,
    SleepStage,
    DailyActivitySummary,
    ActivityType,
    ActivitySummary,
    Activity,
)

TCX_FILE_URL = "https://api.fitbit.com/1/user/-/activities/{}.tcx"
FILE_URL_MAPPING = {
    "intra-day-heart-rate-series.json": "https://api.fitbit.com/1/user/-/activities/heart/date/{}/1d/1sec.json",
    "activities.json": "https://api.fitbit.com/1/user/-/activities/date/{}.json",
    "sleep.json": "https://api.fitbit.com/1.2/user/-/sleep/date/{}.json",
}

ARCHIVAL_FILE_LISTING = FILE_URL_MAPPING.keys()

with open("config.json") as config_file_handler:
    config = json.load(config_file_handler)
    timescale_host = config["timescale_host"]
    timescale_port = config["timescale_port"]
    timescale_user = config["timescale_user"]
    timescale_password = config["timescale_password"]
    timescale_database = config["timescale_database"]
    timescale_ssl_string = config["timescale_ssl_string"]
    start_timestamp = arrow.get(config["start_date"])
    fitbit_data_archival_folder = config["fitbit_data_archival_folder"]

POSTGRES_STR = f"postgresql://{timescale_user}:{timescale_password}@{timescale_host}:{timescale_port}/{timescale_database}?sslmode={timescale_ssl_string}"

engine = create_engine(POSTGRES_STR, echo=True)


def return_formatted_string(arrow_object):
    return arrow_object.format("YYYY-MM-DD")


def parse_rate_zone_info(heart_rate_zone_summary):
    zone_info_map = {}
    column_name_to_key_map = {
        "Out of Range": "out_of_range",
        "Fat Burn": "fat_burn",
        "Cardio": "cardio",
        "Peak": "peak",
    }
    for zone in heart_rate_zone_summary:
        zone_name = zone["name"]
        minutes = zone.get("minutes", -1)
        zone_info_map[column_name_to_key_map[zone_name]] = minutes
    return zone_info_map


def parse_heart_rate_data(folder_path):
    file_path = join(folder_path, "intra-day-heart-rate-series.json")
    assert isfile(file_path)
    parsed_objects = []
    with open(file_path, "r") as intra_day_heart_rate_series_file_handler:
        intra_day_heart_rate_series_obj = json.load(
            intra_day_heart_rate_series_file_handler
        )
        heart_rate_summary = intra_day_heart_rate_series_obj["activities-heart"][0]
        date = heart_rate_summary["dateTime"]
        # TODO: write and assertion for date to be of a certain format.
        # Needed as the field says dateTime and can't be sure when it gets shifted.
        zone_info = parse_rate_zone_info(heart_rate_summary["value"]["heartRateZones"])
        resting_heart_rate = heart_rate_summary["value"].get("restingHeartRate", -1)
        parsed_objects.append(
            HeartRateSummary(
                time_stamp=arrow.get(date).datetime,
                resting_heart_rate=resting_heart_rate,
                out_of_range=zone_info["out_of_range"],
                fat_burn=zone_info["fat_burn"],
                cardio=zone_info["cardio"],
                peak=zone_info["peak"],
            )
        )
        day_series = intra_day_heart_rate_series_obj["activities-heart-intraday"][
            "dataset"
        ]
        for series_obj in day_series:
            time = series_obj["time"]
            value = series_obj["value"]
            total_timestamp = arrow.get(f"{date} {time}")
            parsed_objects.append(
                HeartRate(time_stamp=total_timestamp.datetime, heart_rate=value)
            )
    return parsed_objects


# Resolution for fitbit's sleep metrics is 30 seconds right now.
# It was 60 second when it started.
FITBIT_SLEEP_CAPTURE_INTERVAL = 30


def parse_classic_sleep_info(sleep_info):
    parsed_classic_sleep_info_objs = []
    levels = sleep_info.get("levels", None)
    data = levels.get("data", None)
    for instant in data:
        instant_start = arrow.get(instant.get("dateTime"))
        duration = instant.get("seconds")
        level = instant.get("level")
        for offset_seconds in range(0, duration, FITBIT_SLEEP_CAPTURE_INTERVAL):
            current_instant = instant_start.shift(seconds=offset_seconds)
            parsed_classic_sleep_info_objs.append(
                SleepClassicInfo(
                    time_stamp=current_instant.datetime,
                    sleep_level=SleepLevel[level],
                    sleep_level_value=SleepLevel[level].value,
                )
            )
    # The classic sleep info doesn't seem to have "shortData"
    assert levels.get("shortData", None) is None
    return parsed_classic_sleep_info_objs


def parse_stages_sleep_info(sleep_info):
    parsed_stages_sleep_info_objs = []
    time_stamp_indexed_sleep_dict = {}

    levels = sleep_info.get("levels", None)

    sleep_data = levels.get("data", None)
    for instant in sleep_data:
        instant_start = arrow.get(instant.get("dateTime"))
        duration = instant.get("seconds")
        level = instant.get("level")
        for offset_seconds in range(0, duration, FITBIT_SLEEP_CAPTURE_INTERVAL):
            current_instant = instant_start.shift(seconds=offset_seconds)
            time_stamp_indexed_sleep_dict[
                current_instant.timestamp()
            ] = SleepStagesInfo(
                time_stamp=current_instant.datetime,
                sleep_stage=SleepStage[level],
                sleep_stage_value=SleepStage[level].value,
            )

    short_data = levels.get("shortData", None)
    for wake_instant in short_data:
        instant_start = arrow.get(wake_instant.get("dateTime"))
        duration = wake_instant.get("seconds")
        level = wake_instant.get("level")
        assert level == "wake"
        for offset_seconds in range(0, duration, FITBIT_SLEEP_CAPTURE_INTERVAL):
            current_instant = instant_start.shift(seconds=offset_seconds)
            time_stamp_indexed_sleep_dict[
                current_instant.timestamp()
            ] = SleepStagesInfo(
                time_stamp=current_instant.datetime,
                sleep_stage=SleepStage[level],
                sleep_stage_value=SleepStage[level].value,
            )
    return list(time_stamp_indexed_sleep_dict.values())


def parse_detailed_sleep_info(sleep_info):
    parsed_sleep_info = []
    assert sleep_info["type"] in ["classic", "stages"]
    if sleep_info["type"] == "classic":
        parsed_sleep_info.extend(parse_classic_sleep_info(sleep_info))
    elif sleep_info["type"] == "stages":
        parsed_sleep_info.extend(parse_stages_sleep_info(sleep_info))
    else:
        # Currently we only know about classic and stages.
        print("Found an unexpected sleep type")
        sys.exit(-1)
    return parsed_sleep_info


def parse_sleep_zone_info(folder_path):
    short_data_levels = set()
    file_path = join(folder_path, "sleep.json")
    assert isfile(file_path)
    parsed_objects = []
    with open(file_path, "r") as sleep_file_handler:
        sleep_obj = json.load(sleep_file_handler)
        sleep_data = sleep_obj["sleep"]
        sleep_record_dates = set()
        # sleep is an array here. Need to parse all the sleeps per day.
        for each_sleep in sleep_data:
            sleep_record_dates.add(each_sleep.get("dateOfSleep"))
            parsed_objects.extend(parse_detailed_sleep_info(each_sleep))
        # sleep_record_dates can be either of length ->
        # 0 -> No sleeps are recorded on a day
        # 1 -> Sleeps are recorded and all of them belong to same day. This is due to our assumption of downloading only single day's data at a time.
        assert len(sleep_record_dates) < 2
        # Don't create a sleep summary if no sleep are recorded.
        if len(sleep_record_dates) == 1:
            # Moving summary to end as the date needs to be parsed from individual sleep records
            sleep_summary = sleep_obj.get("summary", None)
            if sleep_summary is not None:
                total_sleep_time = sleep_summary.get("totalMinutesAsleep", None)
                total_time_in_bed = sleep_summary.get("totalTimeInBed", None)
                num_sleeps = sleep_summary.get("totalSleepRecords", None)
                # https://stackoverflow.com/a/59841/8730225
                time_stamp = arrow.get(next(iter(sleep_record_dates)))
                sleep_summary_data_obj = SleepSummary(
                    time_stamp=time_stamp.datetime,
                    num_sleeps=num_sleeps,
                    total_time_in_bed=total_time_in_bed,
                    total_sleep_time=total_sleep_time,
                )
                sleep_stages_summary = sleep_summary.get("stages", None)
                if sleep_stages_summary is not None:
                    sleep_summary_data_obj.stage_deep_duration = (
                        sleep_stages_summary.get("deep", None)
                    )
                    sleep_summary_data_obj.stage_light_duration = (
                        sleep_stages_summary.get("light", None)
                    )
                    sleep_summary_data_obj.stage_rem_duration = (
                        sleep_stages_summary.get("rem", None)
                    )
                    sleep_summary_data_obj.stage_wake_duration = (
                        sleep_stages_summary.get("wake", None)
                    )
                parsed_objects.append(sleep_summary_data_obj)
    return parsed_objects


def parse_daily_activity_summary(activity, date):
    number_of_activites = len(activity["activities"])
    summary = activity["summary"]
    steps = summary["steps"]
    sedentary_minutes = summary["sedentaryMinutes"]
    fairly_active_minutes = summary["fairlyActiveMinutes"]
    lightly_active_minutes = summary["lightlyActiveMinutes"]
    very_active_minutes = summary["veryActiveMinutes"]
    elevation = summary["elevation"]
    floors = summary["floors"]
    return DailyActivitySummary(
        time_stamp=date.datetime,
        steps=steps,
        floors=floors,
        elevation=elevation,
        number_of_activites=number_of_activites,
        sedentary_minutes=sedentary_minutes,
        lightly_active_minutes=lightly_active_minutes,
        fairly_active_minutes=fairly_active_minutes,
        very_active_minutes=very_active_minutes,
    )


def parse_activity_summaries(activities):
    parsed_activity_summaries = []
    for activity in activities:
        time_stamp = arrow.get(activity["startDate"] + " " + activity["startTime"])

        activity_id = activity["logId"]
        distance = activity.get("distance", 0) * 1000
        # Metres FTW
        steps = activity.get("steps", 0)
        duration = activity.get("duration", 0) / 1000
        # Seconds is enough granularity
        calories = activity.get("calories", 0)
        activity_type = ActivityType[
            activity["activityParentName"].replace(" ", "_").lower()
        ]
        parsed_activity_summaries.append(
            ActivitySummary(
                time_stamp=time_stamp.datetime,
                activity_id=activity_id,
                distance=distance,
                steps=steps,
                duration=duration,
                calories=calories,
                activity_type=activity_type,
            )
        )
    return parsed_activity_summaries


def ignore_tz_string(time_stamp_string):
    if time_stamp_string.count("+") > 0:  # 2019-07-16T06:11:35.000+05:30
        return time_stamp_string.split("+")[0]
    else:  # # 2019-07-16T06:11:35.000-08:00
        return "-".join(time_stamp_string.split("-")[0:-1])


def parse_heart_beat(indexed_track_point_data):
    if "HeartRateBpm" in indexed_track_point_data:
        return indexed_track_point_data["HeartRateBpm"][0].text
    else:
        return None


def parse_lat_long(indexed_track_point_data):
    if "Position" in indexed_track_point_data:
        return (
            indexed_track_point_data["Position"][0].text,
            indexed_track_point_data["Position"][1].text,
        )
    else:
        return (None, None)


def parse_activity_details(activity_log_id, folder_path):
    seconds_dedup_cache = {}
    xml_file = join(folder_path, str(activity_log_id) + ".xml")
    activity_root = ET.parse(xml_file).getroot()
    # TrainingCenterDatabase -> Activities -> Activity
    activity_content = activity_root[0][0]
    for elem in activity_content:
        if elem.tag.find("Lap") > -1:
            for sub_tag in elem:
                if (
                    sub_tag.tag
                    == "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}Track"
                ):
                    for track_point in sub_tag:
                        assert (
                            track_point.tag
                            == "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}Trackpoint"
                        )
                        indexed_track_point_data = {}
                        for track_point_sub_tag in track_point:
                            indexed_track_point_data[
                                track_point_sub_tag.tag.replace(
                                    "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}",
                                    "",
                                )
                            ] = track_point_sub_tag
                        time_stamp = arrow.get(
                            ignore_tz_string(indexed_track_point_data["Time"].text)
                        )
                        latitude, longitude = parse_lat_long(indexed_track_point_data)
                        altitude = indexed_track_point_data["AltitudeMeters"].text
                        distance = indexed_track_point_data["DistanceMeters"].text
                        heart_rate = parse_heart_beat(indexed_track_point_data)

                        epoch_sec = int(
                            time_stamp.timestamp()
                        )  # rounding of milli-seconds component.

                        seconds_dedup_cache[epoch_sec] = Activity(
                            time_stamp=time_stamp.datetime,
                            co_ordinates=f"SRID=4326;POINT({latitude} {longitude})",
                            altitude=altitude,
                            distance=distance,
                            heart_rate=heart_rate,
                            activity_id=str(activity_log_id),
                        )
    return seconds_dedup_cache.values()


def parse_activity_info(folder_path):
    file_path = join(folder_path, "activities.json")
    assert isfile(file_path)
    parsed_objects = []
    with open(file_path, "r") as activity_file_handler:
        activity_obj = json.load(activity_file_handler)
        current_date = folder_path.split(sep)[-1]
        current_date_obj = arrow.get(current_date)
        parsed_objects.append(
            parse_daily_activity_summary(activity_obj, current_date_obj)
        )
        parsed_objects.extend(parse_activity_summaries(activity_obj["activities"]))
        for activity in activity_obj["activities"]:
            parsed_objects.extend(
                parse_activity_details(activity["logId"], folder_path)
            )
    return parsed_objects


def get_archived_files(folder_path):
    if isdir(folder_path):
        return [f for f in listdir(folder_path) if isfile(join(folder_path, f))]
    else:
        return None


def get_activity_log_file_names(date_string_folder_path):
    activity_filename = join(date_string_folder_path, "activities.json")
    with open(activity_filename) as activity_file_handler:
        activity_obj = json.load(activity_file_handler)
        activities_list = activity_obj["activities"]
        activity_logIds = [activity["logId"] for activity in activities_list]
    return [(str(activity_logId) + ".xml") for activity_logId in activity_logIds]


def does_folder_contain_all_the_data(folder_path):
    folder_listing = get_archived_files(folder_path)

    remaining_files = [
        file for file in ARCHIVAL_FILE_LISTING if (file not in folder_listing)
    ]

    if len(remaining_files) != 0:
        return False

    tcx_log_file_names = get_activity_log_file_names(folder_path)
    remaining_tcx_log_files = [
        tcx_file for tcx_file in tcx_log_file_names if (tcx_file not in folder_listing)
    ]
    if len(remaining_tcx_log_files) != 0:
        return False

    return True


def get_folders_that_need_processing(earliest_time_stamp):
    folder_list = []
    for file in listdir(fitbit_data_archival_folder):
        file_path = join(fitbit_data_archival_folder, file)
        if isdir(file_path):
            date_for_folder_name = arrow.get(file)
            if date_for_folder_name < earliest_time_stamp:
                pass
            else:
                folder_list.append(file_path)
    return folder_list


def get_earliest_time_stamp(session):
    last_recorded_heart_rate_timestamp = (
        session.query(func.max(HeartRate.time_stamp)).one()[0] or start_timestamp
    )
    last_recorded_heart_rate_summary_timestamp = (
        session.query(func.max(HeartRateSummary.time_stamp)).one()[0] or start_timestamp
    )
    return min([last_recorded_heart_rate_timestamp, last_recorded_heart_rate_timestamp])


def main():
    Base.metadata.create_all(engine, checkfirst=True)
    with sessionmaker(bind=engine)() as session:
        earliest_time_stamp = get_earliest_time_stamp(session)
        folder_list = get_folders_that_need_processing(start_timestamp)
        sorted_folder_list = sorted(folder_list, reverse=True)
        for each_folder in sorted_folder_list:
            assert does_folder_contain_all_the_data(each_folder) == True
            parsed_heart_rate_objects = parse_heart_rate_data(each_folder)
            session.add_all(parsed_heart_rate_objects)
            parsed_sleep_objects = parse_sleep_zone_info(each_folder)
            session.add_all(parsed_sleep_objects)
            parsed_activity_objects = parse_activity_info(each_folder)
            session.add_all(parsed_activity_objects)
        session.commit()


if __name__ == "__main__":
    main()