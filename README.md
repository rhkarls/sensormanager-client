# sensormanager-client
Python client for sensormanager.net cloud data acquisition platform

API methods for retrieving sensor metadata and data to pandas DataFrames. 
Please note that the API is not documented and the methods here are reverse engineered.

## Installation

    pip install git+https://github.com/rhkarls/sensormanager-client
	
or

Place \sensormanagerclient\sensormanagerclient.py in `PYTHONPATH`

Requires:

    `python >= 3.8`
    `requests`
    `pandas`

## Example usage


```python
from sensormanagerclient import SensormanagerSession

# create a session
sms = SensormanagerSession('user', 'password')

# print available stations with id and name
sms.print_station_names()
    id: name
123456: Station A
234567: Station B

# print sensor channels of a given station
sms.print_sensor_channels(123456)
                       description
sensor_id                         
1111         Water Column in meter
2222       Water Temperature in ˚C
3333               HK Battery in V
4444          HK Temperature in ˚C
5555              HK Humidity in %

# get data of a given sensor
sms.get_data_sensor_id(1111,'2020-06-01','2020-07-01')

123456 Station A
2020-06-01 00:00:00    0.728
2020-06-01 00:10:01    0.729
2020-06-01 00:20:00    0.728
2020-06-01 00:30:00    0.729
2020-06-01 00:40:00    0.728
						...
2020-07-01 23:10:00    0.939
2020-07-01 23:20:00    0.939
2020-07-01 23:30:00    0.938
2020-07-01 23:40:00    0.940
2020-07-01 23:50:00    0.941
Name: Gauge m, Length: 4464, dtype: float64

# get all sensors of a given station/logger
data = sms.get_data_logger_id(123456,'2020-06-01','2020-07-01')

                          Gauge m  WTemp ˚C  HKBat V  HKTemp ˚C  HKHum %
123456 Station A                                                
2020-06-01 00:00:00         0.728      6.35    3.611       4.77     18.5
2020-06-01 00:10:01         0.729      6.40    3.677       4.70     18.5
2020-06-01 00:20:00         0.728      6.50    3.678       4.57     18.5
2020-06-01 00:30:00         0.729      6.45    3.688       4.45     18.5
2020-06-01 00:40:00         0.728      6.45    3.688       4.35     18.5
                          ...       ...      ...       ...      ...
2020-07-01 23:10:00         0.939     14.80    3.607       7.19     19.4
2020-07-01 23:20:00         0.939     14.80    3.694       7.15     19.4
2020-07-01 23:30:00         0.938     14.80    3.609       7.11     19.4
2020-07-01 23:40:00         0.940     14.75    3.607       7.07     19.4
2020-07-01 23:50:00         0.941     14.75    3.607       7.03     19.4

[4464 rows x 5 columns]

# clean data (note: static method)
# Check if index is all dates: Throws exception if not
# Check if data is numeric: Converts to numeric if not
# If round_timestamp_freq is passed: round timestamp to this frequency
# Drops duplicate indicies
# Sorts data by index (i.e. Timestamp)

sms.clean_data(data, round_timestamp_freq='10T')
```

## Methods:

See doc strings for methods for more details

`print_station_names`: Prints available station ids with names.

`print_sensor_channels`: Prints available sensor id/channels for a given station id.

`get_data_sensor_id`: Get data for a given sensor id.

`get_data_logger_id`: Get data for a given logger/station id.

`clean_data`: Static method for basic sanitation and check of data.
