from shutil import move
from os import listdir, makedirs
from os.path import isfile, join, isdir
import json

import requests
import arrow


TCX_FILE_URL = "https://api.fitbit.com/1/user/-/activities/{}.tcx"
FILE_URL_MAPPING = {
    "intra-day-heart-rate-series.json": "https://api.fitbit.com/1/user/-/activities/heart/date/{}/1d/1sec.json",
    "activities.json": "https://api.fitbit.com/1/user/-/activities/date/{}.json",
    "sleep.json": "https://api.fitbit.com/1.2/user/-/sleep/date/{}.json",
}

ARCHIVAL_FILE_LISTING = FILE_URL_MAPPING.keys()

config = {}
with open("config.json") as config_file_handler:
    config = json.load(config_file_handler)


def get_folder_path(date_string):
    return join(config["fitbit_data_archival_folder"], date_string)


def get_archived_files(folder_path):
    if isdir(folder_path):
        return [f for f in listdir(folder_path) if isfile(join(folder_path, f))]
    else:
        return None


def download_file(url, file_path, json_flag=True):
    temp_file_path = file_path + "_bk"
    response = requests.get(
        url, headers={"Authorization": "Bearer " + config["fitbit_token"]}
    )
    try:
        response.raise_for_status()
        if json_flag:
            json_response = response.json()
            with open(temp_file_path, "w") as file_write_handler:
                json.dump(json_response, file_write_handler)
        else:
            xml_response = response.text
            with open(temp_file_path, "w") as file_write_handler:
                file_write_handler.write(xml_response)
        move(temp_file_path, file_path)
    except requests.exceptions.HTTPError:
        print("Status code is " + str(response.status_code))
        print("Response headers are " + str(response.headers))
        print("Response is " + response.text)


def get_activity_log_file_names(date_string_folder_path):
    activity_filename = join(date_string_folder_path, "activities.json")
    with open(activity_filename) as activity_file_handler:
        activity_obj = json.load(activity_file_handler)
        activities_list = activity_obj["activities"]
        activity_logIds = [activity["logId"] for activity in activities_list]
    return [(str(activity_logId) + ".xml") for activity_logId in activity_logIds]


def ensure_download(date_string):
    date_string_folder_path = get_folder_path(date_string)
    folder_listing = get_archived_files(date_string_folder_path)
    if folder_listing is None:
        makedirs(date_string_folder_path)
        folder_listing = []

    remaining_files = [
        file for file in ARCHIVAL_FILE_LISTING if (file not in folder_listing)
    ]
    for remaining_file in remaining_files:
        url = FILE_URL_MAPPING[remaining_file].format(date_string)
        file_path = join(date_string_folder_path, remaining_file)
        download_file(url, file_path)

    tcx_log_file_names = get_activity_log_file_names(date_string_folder_path)
    remaining_tcx_log_files = [
        tcx_file for tcx_file in tcx_log_file_names if (tcx_file not in folder_listing)
    ]
    for each_tcx_file in remaining_tcx_log_files:
        url = TCX_FILE_URL.format(each_tcx_file.split(".")[0])
        file_path = join(date_string_folder_path, each_tcx_file)
        download_file(url, file_path, json_flag=False)


def return_formatted_string(arrow_object):
    return arrow_object.format("YYYY-MM-DD")


def main():
    start_date = arrow.get(config["start_date"])
    current_date = start_date
    while (arrow.now() - current_date).days > 1:
        ensure_download(return_formatted_string(current_date))
        # Advancing date to next..
        current_date = current_date.shift(days=1)


if __name__ == "__main__":
    main()