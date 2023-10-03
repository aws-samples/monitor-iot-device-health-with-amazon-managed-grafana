# monitor-iot-device-health-with-amazon-managed-grafana

This CDK constructs provides sample serverless solution for monitoring your IoT devices with Amazon Managed Grafana. 


### Prerequisites

To get started, make sure you have the following prerequisites:

* An AWS profile with permissions to create AWS Identity and Access Management (IAM) roles, Studio domains, and Studio user profiles.
* The AWS Command Line Interface (https://aws.amazon.com/cli/) (AWS CLI) installed and configured with credentials to access your account. 
* NodeJS and NPM (https://nodejs.org/en/download) - required by the AWS CDK.
* The AWS CDK (https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) installed. For more information, refer to Getting started with the AWS CDK. 
* Python 3+ (https://wiki.python.org/moin/BeginnersGuide/Download) and the CDK libraries for Python (https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-python.html).

### Deploying AWS CDK constructs

*To deploy your AWS CDK stack, run the following commands in the location where you cloned the repository*

The command may be “python” instead of “python3” depending on your path configurations. If using python you will need to edit the file cdk.json and change the first line from "app": "python3 app.py" to "app": "python app.py"

**Create a virtual environment.**

* For macOS/Linux, use python3 -m venv .venv
* For Windows, use python3 -m venv .venv

**Activate the virtual environment.**

* For macOS/Linux, use source .venv/bin/activate
* For Windows, use .venv\Scripts\activate.bat
* For Powershell, use .venv\Scripts\activate.ps1

**Install the required dependencies.**

* pip install -r requirements.txt

At this point you can optionally synthesize the CloudFormation template for this code:

cdk synth

 **Deploy the solution** 

* cdk bootstrap 
* cdk deploy 

## Clean up

**Delete the AWS CDK stack**

When you’re done with the resources you created, you can destroy your AWS CDK stack by running the following command in the location where you cloned the repository: 

* cdk destroy

When asked to confirm the deletion of the stack, enter yes.

You can also delete the stack on the AWS CloudFormation console with the following steps:

1. Open the AWS CloudFormation console, choose Stacks in the navigation pane.
2. Choose the stack that you want to delete.
3. In the stack details pane, choose Delete.
4. Choose Delete stack when prompted.

If you run into any errors you may have to manually delete some resources depending on your account configuration. 