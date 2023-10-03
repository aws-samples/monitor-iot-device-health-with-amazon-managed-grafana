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

import boto3
import json
import os
import urllib3
import uuid

# create grafana api key with boto
# returns API key
def create_grafana_api_key(workspace_id):
    grafana = boto3.client('grafana')

    response = grafana.create_workspace_api_key(
        keyName='admin_key' + str(uuid.uuid4()),
        keyRole='ADMIN',
        secondsToLive=600, # 10 minutes
        workspaceId=workspace_id
    )

    return response['key']


# create timestream data source in grafana
# returns data souce uid
def create_timestream_data_source(workspace_id, http):

    database_name = os.environ['TimestreamDatabase']
    table_name = os.environ['TimestreamTable']
    
    # check if data source already exists
    api_url = "https://"+workspace_id+".grafana-workspace.us-east-1.amazonaws.com/api/datasources"
    result = http.request('GET', api_url)
    data = json.loads(result.data.decode('utf-8'))

    # if data source already exists, return uid
    for item in data:
        if item['database'] == '"'+database_name+'"':
            return item['uid']



    # otherwise, create data source
    api_url = "https://"+workspace_id+".grafana-workspace.us-east-1.amazonaws.com/api/datasources"
    payload = {
        "orgId": 1,
        "name": "Amazon Timestream us-east-1"  + str(uuid.uuid4()),
        "type": "grafana-timestream-datasource",
        "typeName": "Amazon Timestream",
        "typeLogoUrl": "public/plugins/grafana-timestream-datasource/img/timestream.svg",
        "access": "proxy",
        "url": "",
        "user": "",
        "database": '"'+database_name+'"',
        "basicAuth": False,
        "isDefault": False,
        "jsonData": {
            "authType": "ec2_iam_role",
            "defaultDatabase": '"'+database_name+'"',
            "defaultMeasure": "",
            "defaultRegion": "us-east-1",
            "defaultTable": '"'+table_name+'"'
        },
        "readOnly": False
    } 

    result = http.request('POST', api_url, body=json.dumps(payload))
    
    return json.loads(result.data.decode('utf-8'))['datasource']['uid']

# create timestream dashboard in grafana
def create_timestream_dashboard(workspace_id, http, datasource_uid):

    # search for grafana dashboard matching name
    api_url = "https://"+workspace_id+".grafana-workspace.us-east-1.amazonaws.com/api/search?tag="+datasource_uid
    result = http.request('GET', api_url)
    data = json.loads(result.data.decode('utf-8'))
    
    # if dashboard already exists, return url
    for item in data:
        if item['title'] == "IoT Device Dashboard":
            return item['url']

    api_url = "https://"+workspace_id+".grafana-workspace.us-east-1.amazonaws.com/api/dashboards/db"

    database_name = os.environ['TimestreamDatabase']

    with open(f'grafana_dashboard.json', encoding='utf-8') as f:
        data = f.read()
        data = data.replace('DATASOURCE_UID', datasource_uid)
        data = data.replace('IOT_TELEMETRY_DATABASE', database_name)
        payload = json.loads(data)
    
    result = http.request('POST', api_url, body=json.dumps(payload))

    return json.loads(result.data.decode('utf-8'))['url']

# lambda handler
def lambda_handler(event, context):
    print(event)
    print(context)

    workspace_id = os.environ['grafana_workspace_id']
    print(workspace_id)

    api_key = create_grafana_api_key(workspace_id)
    print(api_key)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key
        }
    
    http = urllib3.PoolManager(headers=headers)
    datasource_uid = create_timestream_data_source(workspace_id, http)
    print(datasource_uid)

    url = create_timestream_dashboard(workspace_id, http, datasource_uid)
    print(url)
    
    # return url to cloudformation
    return url

    

