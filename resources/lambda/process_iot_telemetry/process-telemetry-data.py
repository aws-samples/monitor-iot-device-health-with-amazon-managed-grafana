#################################################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.                            #
# SPDX-License-Identifier: MIT-0                                                                #
#                                                                                               #
# Permission is hereby granted, free of charge, to any person obtaining a copy of this          #
# software and associated documentation files (the "Software"), to deal in the Software         #
# without restriction, including without limitation the rights to use, copy, modify,            #
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to            #
# permit persons to whom the Software is furnished to do so.                                    #
#                                                                                               #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,           #
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A                 #
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT            #
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION             #
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE                #
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                                        #
#################################################################################################

import json
import boto3
import os
from botocore.config import Config


### Often IoT devices do not include important metadata about the device in the telemetry payload.
### This could include the customer or location where the device is deployed or the id of the equipment being monitored
### This metadata is often stored in an applicatoin database such as DynamoDB or Aurora SQL
### For simplicity here it is loaded from a local JSON file and added to the telemetry record in timestream
with open(f"device-meta.json", encoding="utf-8") as meta:
    deviceMeta = json.load(meta)

### Setup database connection outside handler for optimal reuse
database = os.environ["TimestreamDatabase"]
table = os.environ["TimestreamTable"]

session = boto3.Session()
write_client = session.client(
    "timestream-write",
    config=Config(
        read_timeout=20, max_pool_connections=5000, retries={"max_attempts": 10}
    ),
)


def lambda_handler(event, context):
    ### lambda recieves IoT telemetry payload from IoT Rule. the Rule sends one payload even per invocation ###
    telemetry = event

    dimensions = [{"Name": "deviceid", "Value": telemetry["deviceid"]}]

    equipmentid = deviceMeta[telemetry["deviceid"]]["equipmentid"]
    customerid = deviceMeta[telemetry["deviceid"]]["customerid"]

    ### Setup telemetry values record
    values = {
        "Dimensions": dimensions,
        "MeasureName": "telemetry",
        "MeasureValues": [
            {
                "Name": "temperature",
                "Value": str(telemetry["temperature"]),
                "Type": "BIGINT",
            },
            {
                "Name": "signal_strength",
                "Value": str(telemetry["signal_strength"]),
                "Type": "DOUBLE",
            },
            {
                "Name": "latitude",
                "Value": str(telemetry["location"]["latitude"]),
                "Type": "DOUBLE",
            },
            {
                "Name": "longitude",
                "Value": str(telemetry["location"]["longitude"]),
                "Type": "DOUBLE",
            },
            {
                "Name": "fuel_level",
                "Value": str(telemetry["fuel_level"]),
                "Type": "DOUBLE",
            },
            {
                "Name": "battery_level",
                "Value": str(telemetry["battery_level"]),
                "Type": "DOUBLE",
            },
            {"Name": "equipmentid", "Value": equipmentid, "Type": "VARCHAR"},
            {"Name": "customerid", "Value": customerid, "Type": "VARCHAR"},
        ],
        "MeasureValueType": "MULTI",
        "Time": str(telemetry["timestamp"]),
    }

    records = [values]


    ### Send telemetry to timestream as a single record
    try:
        result = write_client.write_records(
            DatabaseName=database, TableName=table, Records=records, CommonAttributes={}
        )
        print(
            "WriteRecords Status: [%s]" % result["ResponseMetadata"]["HTTPStatusCode"]
        )
    except write_client.exceptions.RejectedRecordsException as err:
        print("RejectedRecords: ", err)
        for rr in err.response["RejectedRecords"]:
            print("Rejected Index " + str(rr["RecordIndex"]) + ": " + rr["Reason"])
        print("Other records were written successfully. ")
    except Exception as err:
        print("Error:", err)
        pass
