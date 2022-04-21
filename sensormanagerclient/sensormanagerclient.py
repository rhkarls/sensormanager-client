# -*- coding: utf-8 -*-
"""
Methods for accessing data from sensormanager.net
sensormanager.net is not documented and the methods here are reverse engineered.

Only tested with provider sts_back (STS Sensors), might not work with others depending
on the backend version and other unknown differences.

License: MIT
Copyright (c) 2021 Reinert Huseby Karlsen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import json
import time
import hashlib
import warnings
import logging
import dateutil
import datetime as dt
from io import StringIO

import requests
import pandas as pd


class SensormanagerSession:
    def __init__(self, username, password, provider="sts_back"):
        """Authenticate with username and password for sensormanager.net"""
        self.provider = provider

        self.api_s = requests.Session()
                
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:77.0) Gecko/20100101 Firefox/77.0'
        headers = {'User-Agent': user_agent}
        
        self.api_s.headers.update(headers)

        hash_password = hashlib.md5(password.encode("utf-8")).hexdigest()

        self.auth_url_t = (
            f"https://www.sensormanager.net/{self.provider}/services?"
            f"_ScriptTransport_id=2&nocache"
            f"={int(time.time())}"
            f"&_ScriptTransport_data="
            f'{{"service":"qooxdoo.ttBasic","method":"validateLoginCredentials",'
            f'"id":2,"params":["{username}","{hash_password}"]}}'
        )

        r_auth_response = self._authenticate()

        if r_auth_response["result"][0] == "-1":
            raise AuthenticationError
        else:
            self._get_sensors()
            self._set_id_dicts()

    def _authenticate(self):
        """ Authenticate with server, can be used to re-auth in case of timeouts etc"""
        r_auth = self.api_s.post(self.auth_url_t)

        # Note that .status_code always is returned 200, not working on this api call
        r_auth_response = json.loads(r_auth.content[50:-2])
        
        return r_auth_response
    
    def _reconnect(self):
        logging.info("_reconnect called")
        
        r_auth_response = self._authenticate()
        
        if r_auth_response["result"][0] == "-1":
            raise AuthenticationError
        else:
            return

    def close(self):
        self.api_s.close()

    def _get_sensors(self):

        get_sensors_url_t = (
            f"https://www.sensormanager.net/{self.provider}/services/"
            f"index.php?_ScriptTransport_id=2&nocache"
            f"={int(time.time())}"
            f"&_ScriptTransport_data="
            f'{{"service":"qooxdoo.measurements",'
            f'"method":"getSensorTree","id":2,"params":[]}}'
        )

        r_get_sensors = self.api_s.get(get_sensors_url_t)

        # list of sensors
        self.sensor_list = json.loads(r_get_sensors.content[50:-2])["result"]["loggers"]

    def _set_id_dicts(self):
        self.station_df = pd.DataFrame(self.sensor_list)
        self.station_df.set_index("serial", inplace=True)

        # create dicts of
        self.logger_id_sensor_id = {}  # station serial and list of sensor id
        self.location_str_logger_id = {}  # station string name and serial
        self.sensor_id_param_name = {}  # all sensor id full descriptions

        for i, r in self.station_df.iterrows():
            r_sids = []
            for sens in r.sensors:
                r_sids.append(sens["id"])
                self.sensor_id_param_name[sens["id"]] = sens  # full description dict
            self.logger_id_sensor_id[i] = r_sids

            self.location_str_logger_id[r["name"]] = i

    def print_station_names(self):
        """Prints available station ids with names"""

        print("    id: name")

        for sn, sid in self.location_str_logger_id.items():
            print(f"{sid}: {sn}")

    def print_sensor_channels(self, station_id):
        """Prints available sensor id/channels for a given station id"""
        # get sensor ids belonging to station_id and print as dataframe
        sensors = self.station_df.loc[str(station_id), "sensors"]

        sensors_df = pd.DataFrame(sensors)
        sensors_df = sensors_df[["id", "datatypedescrlong"]]
        sensors_df.columns = ["sensor_id", "description"]

        print(sensors_df.set_index("sensor_id").to_string())

    def get_data_sensor_id(self, sensor_id, date_start, date_end):
        """
        Get data for a given sensor_id in the date range date_start:date_end.

        See print_sensor_channels method for listing sensor_ids for a particular station.

        Parameters
        ----------
        sensor_id : int
            Integer id of sensor (also called channel).
        date_start : str
            String for start date (format '%Y-%m-%d') of data query.
        date_end : str
            String for end date (format '%Y-%m-%d') of data query.

        Raises
        ------
        ValueError
            If date strings cannot be converted to posix time, or date_end is earlier than date_start.

        Returns
        -------
        data_series : pandas.DataFrame
            DataFrame with query result.
            DataFrame has extra attribute sensor_id_dict.

        """

        try:
            date_start_posix = self._ts_str_to_posix_ms(date_start)
        except ValueError as VE:
            raise (VE)

        try:
            date_end_posix = self._ts_str_to_posix_ms(date_end)
        except ValueError as VE:
            raise (VE)

        if date_start_posix >= date_end_posix:
            raise ValueError("date_end must be later than date_start")

        params = {
            "dateStart": date_start_posix,
            "dateEnd": date_end_posix,
            "sensorId": sensor_id,
            "exportType": "csv_short",
        }

        try:
            r_get = self.api_s.get(
                f"https://www.sensormanager.net/{self.provider}/flot/export.php",
                params=params,
            )
        except requests.exceptions.ConnectionError:
            self._reconnect()
            time.sleep(1)
            r_get = self.api_s.get(
                f"https://www.sensormanager.net/{self.provider}/flot/export.php",
                params=params,
            )
            
        s_get = r_get.content.decode("utf-8")
        data_buffer = StringIO(s_get)
        data = pd.read_csv(
            data_buffer,
            sep=";",
            index_col=0,
            skiprows=[1],
            parse_dates=[0],
            on_bad_lines="skip",
        )

        data_series = data[data.columns[0]].copy()

        with warnings.catch_warnings():
            warnings.simplefilter(action="ignore", category=UserWarning)
            data_series.sensor_id_dict = {data_series.name: sensor_id}

        return data_series

    def get_data_logger_id(self, logger_id, date_start, date_end, sleep_between=1):
        """
        Get data for a given logger_id (id of logger, also called station)
        within a date range between date_start and date_end.

        Will get all sensors (aka channels) for the given logger.

        See method print_station_names to list available loggers/stations.

        Parameters
        ----------
        logger_id : int
            Integer id of logger (also called station).
        date_start : str
            String for start date (format '%Y-%m-%d') of data query.
        date_end : str
            String for end date (format '%Y-%m-%d') of data query.
        sleep_between : int, optional
            Seconds to sleep between requesting data from each channel
            To mitigate dropped connection from server
            Default is 1 second.

        Returns
        -------
        data_logger : pandas.DataFrame
            DataFrame with query result.
            DataFrame has extra attribute sensor_id_dict.

        """

        data_logger = pd.DataFrame()

        if isinstance(logger_id, int):
            logger_id = str(logger_id)

        sensor_id_dict = {}
        for sensor_id in self.logger_id_sensor_id.get(logger_id):
            data_sensor = self.get_data_sensor_id(sensor_id, date_start, date_end)
            data_logger = data_logger.join(data_sensor, how="outer")
            sensor_id_dict[sensor_id] = data_sensor.name
            time.sleep(sleep_between)

        with warnings.catch_warnings():
            warnings.simplefilter(action="ignore", category=UserWarning)
            data_logger.sensor_id_dict = sensor_id_dict.copy()

        return data_logger

    @staticmethod
    def clean_data(input_data, round_timestamp_freq=None):
        """
        Basic sanitation and check of data.

        The following checks and adjustments are made:
        - Check if index is all dates: Throws exception if not
        - Check if data is numeric: Converts to numeric if not
        - If round_timestamp_freq is passed: round timestamp to this frequency
        - Drops duplicate indicies
        - Sorts data by index


        Parameters
        ----------
        input_data : pandas.Series or pandas.DataFrame
            The time series input data to be cleaned.
        round_timestamp_freq : str, optional
            Pandas frequency string for rounding the timestamps.
            The default is None, i.e. no rounding takes place.

        Raises
        ------
        NotImplementedError
            If index is not all dates, no corrections implemented.

        Returns
        -------
        clean_data : pandas.Series or pandas.DataFrame
            Cleaned data.

        """

        # copy the sensor_id_dict information
        try:
            sensor_id_dict = input_data.sensor_id_dict.copy()
        except AttributeError:
            sensor_id_dict = {}

        clean_data = input_data.copy()

        # HINT not tested for alternative types to datetime64
        if not input_data.index.inferred_type == "datetime64":
            raise NotImplementedError(
                "Data index is not all dates. Solution not yet implemented"
            )
        
        # check that all columns are numeric dtype
        # for dataframes and series
        try:
            data_is_numeric = input_data.dtypes.apply(
                pd.api.types.is_numeric_dtype
            ).all()
        except AttributeError:
            data_is_numeric = pd.api.types.is_numeric_dtype(input_data.dtype)

        # convert to numeric data if dtypes are not numeric
        if not data_is_numeric:
            clean_data = pd.to_numeric(clean_data, errors="coerce")

        # round timestamps
        if round_timestamp_freq is not None:
            clean_data = SensormanagerSession._round_timestamp(
                clean_data, freq=round_timestamp_freq
            )

        # drop duplicate indicies
        clean_data = SensormanagerSession._drop_duplicates(clean_data)

        # sort by index
        clean_data = clean_data.sort_index()

        # attach the sensor_id_dict
        with warnings.catch_warnings():
            warnings.simplefilter(action="ignore", category=UserWarning)
            clean_data.sensor_id_dict = sensor_id_dict

        return clean_data

    @staticmethod
    def _drop_duplicates(input_data):
        """Drop duplicated indicies from dataframe or series"""

        duplicated_index = input_data.index.duplicated()

        if duplicated_index.sum() > 0:
            df_nd = input_data.loc[~input_data.index.duplicated(keep="first")]
        else:
            df_nd = input_data.copy()

        return df_nd

    @staticmethod
    def _round_timestamp(input_data, freq):
        """Round timestamps do nearest whole frequency freq"""

        input_data_ts_round = input_data.copy()
        input_data_ts_round.index = input_data_ts_round.index.round(freq=freq)

        return input_data_ts_round

    @staticmethod
    def _ts_str_to_posix_ms(ts_str):
        """Return isoformat datestring to posix timestamp in ms UTC time"""

        return int(
            dt.datetime.fromisoformat(ts_str)
            .replace(tzinfo=dateutil.tz.UTC)
            .timestamp()
            * 1000
        )


class AuthenticationError(Exception):
    """Exception raised authentication error to sensormanager
    API does not return status codes for the success of authentication

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Authentication error"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}: Invalid username or password"
