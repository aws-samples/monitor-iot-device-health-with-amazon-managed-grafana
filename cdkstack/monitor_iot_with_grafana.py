import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_timestream as timestream,
    aws_iot as iot,
    aws_grafana as grafana,
    triggers,
    aws_logs as logs
)
from cdk_nag import NagSuppressions


class monitor_iot_with_grafana(Stack):
    def __init__(self, scope: cdk.App, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

##############################################
#  Amazon Timestream setup
##############################################
        ### Create timestream database ###
        iot_telemetry_database = timestream.CfnDatabase(
            self,
            "iot-telemetry",
        )
        iot_telemetry_database.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        cdk.CfnOutput(self, "TimestreamTelemetryDatabase", value=iot_telemetry_database.ref)

        ### Create timestream table ###
        telemetry_timestream_table = timestream.CfnTable(
            self,
            "device-telemetry",
            database_name=iot_telemetry_database.ref,
            table_name="device-telemetry"
        )

        telemetry_timestream_table.add_dependency(iot_telemetry_database)
        telemetry_timestream_table.apply_removal_policy(
            cdk.RemovalPolicy.DESTROY)


##############################################
#  Amazon Managed Grafana workspace setup
##############################################
        ### create policy for grafana to read from timestream ###
        timestream_read_policy = iam.Policy(self, "timestream-read-policy",
                                            statements=[
                                                  iam.PolicyStatement(
                                                      actions=[
                                                          "timestream:DescribeDatabase",
                                                          "timestream:DescribeTable",
                                                          "timestream:ListDatabases",
                                                          "timestream:ListMeasures",
                                                          "timestream:ListTables",
                                                          "timestream:ListTagsForResource",
                                                          "timestream:Select",
                                                          "timestream:DescribeScheduledQuery",
                                                          "timestream:ListScheduledQueries",
                                                          "timestream:DescribeBatchLoadTask",
                                                          "timestream:ListBatchLoadTasks"],
                                                      resources=[iot_telemetry_database.attr_arn,
                                                                 iot_telemetry_database.attr_arn + "/*"]
                                                  ),
                                                iam.PolicyStatement(
                                                      actions=[
                                                          "timestream:CancelQuery",
                                                          "timestream:SelectValues",
                                                          "timestream:DescribeEndpoints"
                                                      ],
                                                      resources=["*"]
                                                  )
                                            ]
                                            )

       ### create role for grafana ###
        grafana_iot_health_workspace_role = iam.Role(self, "Grafana-Role",
                                                     assumed_by=iam.ServicePrincipal(
                                                         "grafana.amazonaws.com"),
                                                     description="Allows Amazon Grafana to access your AWS services"
                                                     )
        grafana_iot_health_workspace_role.attach_inline_policy(
            timestream_read_policy)
        grafana_iot_health_workspace_role.apply_removal_policy(
            cdk.RemovalPolicy.DESTROY)

        NagSuppressions.add_resource_suppressions([timestream_read_policy],
                                                  [{
                                                      "id": "AwsSolutions-IAM5",
                                                      "reason": "Grafana needs to read DB and children",
                                                      "appliesTo": ['Resource::<iottelemetry.Arn>/*', 'Resource::*']
                                                  }],
                                                  apply_to_children=True
                                                  )
        ### create grafana workspace ###
        grafana_iot_health_workspace = grafana.CfnWorkspace(
            self,
            "IoT-Health-Workspace",
            account_access_type="CURRENT_ACCOUNT",
            authentication_providers=["AWS_SSO", "SAML"],
            permission_type="SERVICE_MANAGED",
            name="IoT-Health-Workspace",
            role_arn=grafana_iot_health_workspace_role.role_arn
        )
        grafana_iot_health_workspace.apply_removal_policy(
            cdk.RemovalPolicy.DESTROY)

        cdk.CfnOutput(self, "GrafanaWorkspaceUrl", value="https://" +
                      grafana_iot_health_workspace.get_att("Endpoint").to_string())

        grafana_workspace_id = grafana_iot_health_workspace.get_att(
            "Id").to_string()

##############################################
#  AWS Lambda functions setup
#   1. Process telemetry data from IoT device
#   2. Initalize Grafana dashboard
##############################################

        ### create policy for lambda to write cloudwatch logs ###
        cloudwatch_lambda_policy_statement = iam.PolicyStatement(
            actions=["logs:CreateLogGroup",
                     "logs:CreateLogStream", "logs:PutLogEvents"],
            effect=iam.Effect.ALLOW,
            resources=[Stack.of(self).format_arn(
                service="logs",
                resource="log-group:",
                resource_name="aws/lambda/*"
            )
            ]
        )

        ### create roles for lambda functions ###
        process_telemetry_lambda_role = iam.Role(self, "lambda-role",
                                                 assumed_by=iam.ServicePrincipal(
                                                     "lambda.amazonaws.com")
                                                 )
        process_telemetry_lambda_role.add_to_policy(
            cloudwatch_lambda_policy_statement)

        initialize_grafana_lambda_role = iam.Role(self, "initalize-grafana-lambda-role",
                                                  assumed_by=iam.ServicePrincipal(
                                                      "lambda.amazonaws.com")
                                                  )
        initialize_grafana_lambda_role.add_to_policy(
            cloudwatch_lambda_policy_statement)

        NagSuppressions.add_resource_suppressions([process_telemetry_lambda_role, initialize_grafana_lambda_role],
                                                  [{
                                                      "id": "AwsSolutions-IAM5",
                                                      "reason": "Lambda function needs to be able to create CloudWatch log groups and streams",
                                                      "appliesTo": ['Resource::arn:<AWS::Partition>:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/*']
                                                  }],
                                                  apply_to_children=True
                                                  )

        ### create lambda function to process data from iot core ###
        process_telemetry_lambda_function = _lambda.Function(self, "IotTelemetryToTimestream",
                                                             runtime=_lambda.Runtime.PYTHON_3_11,
                                                             code=_lambda.Code.from_asset(
                                                                 "resources/lambda/process_iot_telemetry"),
                                                             handler="process-telemetry-data.lambda_handler",
                                                             description="Process IoT telemetry data and send to timestream",
                                                             environment={
                                                                 "TimestreamDatabase": iot_telemetry_database.ref,
                                                                 "TimestreamTable": telemetry_timestream_table.table_name
                                                             },
                                                             role=process_telemetry_lambda_role
                                                            #  log_retention=logs.RetentionDays.ONE_DAY
                                                             )

        ### add permissions for timestream to lambda function ###
        lambda_timestream_policy = iam.Policy(self, "lambda-timestream-policy",
                                              statements=[
                                                  iam.PolicyStatement(
                                                      actions=[
                                                          "timestream:WriteRecords",
                                                          "timestream:ListDatabases",
                                                          "timestream:ListTables"
                                                      ],
                                                      resources=[iot_telemetry_database.attr_arn,
                                                                 iot_telemetry_database.attr_arn + "/*"]
                                                  ),
                                                  iam.PolicyStatement(
                                                      actions=[
                                                          "timestream:DescribeEndpoints"
                                                      ],
                                                      resources=["*"]
                                                  )
                                              ]
                                              )

        process_telemetry_lambda_function.role.attach_inline_policy(
            lambda_timestream_policy)
        # lambda_timestream_policy.apply_removal_policy(
        #     cdk.RemovalPolicy.DESTROY)

        NagSuppressions.add_resource_suppressions(lambda_timestream_policy,
                                                  [{
                                                      "id": "AwsSolutions-IAM5",
                                                      "reason": "Timestream requires * access for DescribeEndpoints and full database access",
                                                      "appliesTo": ['Resource::<iottelemetry.Arn>/*', 'Resource::*']
                                                  }],
                                                  apply_to_children=True
                                                  )

        ### create lambda function to initialize grafana workspace ###
        initialize_grafana_dashboard = triggers.TriggerFunction(self, "InitializeGrafanaDashboard",
                                                                handler="dashboard_setup.lambda_handler",
                                                                runtime=_lambda.Runtime.PYTHON_3_11,
                                                                code=_lambda.Code.from_asset(
                                                                    "resources/grafana"),
                                                                description="initialize grafana workspace",
                                                                environment={
                                                                    "grafana_workspace_id": grafana_workspace_id,
                                                                    "TimestreamDatabase": iot_telemetry_database.ref,
                                                                    "TimestreamTable": telemetry_timestream_table.table_name
                                                                },
                                                                role=initialize_grafana_lambda_role
                                                                # log_retention=logs.RetentionDays.ONE_DAY
                                                                )
        initialize_grafana_dashboard.apply_removal_policy(
            cdk.RemovalPolicy.DESTROY)

        ### create arn for grafana workspace ###
        grafana_workspace_arn = Stack.of(self).format_arn(
            service="grafana",
            resource="/workspaces",
            resource_name=grafana_workspace_id
        )

        ### create policy for lambda to access grafana workspace ###
        lambda_grafana_policy = iam.Policy(self, "lambda-grafana-policy",
                                           statements=[
                                               iam.PolicyStatement(
                                                   actions=[
                                                       "grafana:DescribeWorkspace",
                                                       "grafana:CreateWorkspaceApiKey"
                                                   ],
                                                   resources=[
                                                       grafana_workspace_arn]
                                               )
                                           ]
                                           )

        initialize_grafana_dashboard.role.attach_inline_policy(
            lambda_grafana_policy)



##############################################
#  AWS IoT Core Rule setup
##############################################

        ### create iot rule to push to lambda handler ###
        iot_to_lambda_topic_rule = iot.CfnTopicRule(self, "telematics-rule",
                                                    topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                                                        actions=[iot.CfnTopicRule.ActionProperty(
                                                            lambda_=iot.CfnTopicRule.LambdaActionProperty(
                                                                function_arn=process_telemetry_lambda_function.function_arn
                                                            )
                                                        )],
                                                        description="send to lambda handler",
                                                        rule_disabled=False,
                                                        sql='SELECT * from \'sampledevice/data\''
                                                    )
                                                    )

        iot_to_lambda_topic_rule.apply_removal_policy(
            cdk.RemovalPolicy.DESTROY)

        ### add permission for iot rule to lambda function - this allows iot to invoke the lambda function ###
        process_telemetry_lambda_function.add_permission("grant iot rule access",
                                                         principal=iam.ServicePrincipal(
                                                             "iot.amazonaws.com"),
                                                         source_arn=iot_to_lambda_topic_rule.attr_arn
                                                         )
