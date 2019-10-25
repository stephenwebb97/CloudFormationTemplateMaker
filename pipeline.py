from troposphere import Base64, Select, FindInMap, GetAtt
from troposphere import GetAZs, Join, Output, If, And, Not
from troposphere import Or, Equals, Condition
from troposphere import Parameter, Ref, Tags, Template, Sub, Export
from troposphere.sns import Topic, Subscription
from troposphere.cloudformation import CustomResource
from troposphere.codepipeline import (Pipeline, Stages, Actions, ActionTypeId, InputArtifacts, OutputArtifacts,
                                      ConfigurationProperties)
from troposphere.codebuild import (EnvironmentVariable, Environment, Source, Artifacts)


t = Template()

t.add_version("2010-09-09")

t.add_description("""\
(qs-1ph8nehb7)  Serverless CICD Quick Start Codepipeline shared resources and security
""")
AppName = t.add_parameter(Parameter(
    "AppName",
    Description="Application name, used for the repository and child stack name",
    Type="String",
    Default="Sample",
))

BuildImageName = t.add_parameter(Parameter(
    "BuildImageName",
    Description="Docker image for application build",
    Type="String",
    Default="aws/codebuild/nodejs:10.1.0",
))

DevAwsAccountId = t.add_parameter(Parameter(
    "DevAwsAccountId",
    Description="AWS account ID for development account",
    Type="String",
    AllowedPattern="(\\d{12}|^$)",
    ConstraintDescription="Must be an AWS account ID",
    Default="159527342995",
))

ProdAwsAccountId = t.add_parameter(Parameter(
    "ProdAwsAccountId",
    Description="AWS account ID for production account",
    Type="String",
    AllowedPattern="(\\d{12}|^$)",
    ConstraintDescription="Must be an AWS account ID",
    Default="159527342995",
))

Branch = t.add_parameter(Parameter(
    "Branch",
    Description="Repository branch name",
    Type="String",
    Default="master",
))

Suffix = t.add_parameter(Parameter(
    "Suffix",
    Description="Repository branch name (adapted to use in CloudFormation stack name)",
    Type="String",
    Default="master",
))

ArtifactBucket = t.add_parameter(Parameter(
    "ArtifactBucket",
    Description="Artifact S3 bucket",
    Type="String",
))

ArtifactBucketKeyArn = t.add_parameter(Parameter(
    "ArtifactBucketKeyArn",
    Description="ARN of the artifact bucket KMS key",
    Type="String",
))

PipelineServiceRoleArn = t.add_parameter(Parameter(
    "PipelineServiceRoleArn",
    Description="Pipeline service role ARN",
    Type="String",
))

SamTranslationBucket = t.add_parameter(Parameter(
    "SamTranslationBucket",
    Description="S3 bucket for SAM translations",
    Type="String",
))

DynamicPipelineCleanupLambdaArn = t.add_parameter(Parameter(
    "DynamicPipelineCleanupLambdaArn",
    Description="ARN of Lambda function to clean up dynamic pipeline",
    Type="String",
))

SecretArnDev = t.add_parameter(Parameter(
    "SecretArnDev",
    Description="ARN for Secrets Manager secret for dev",
    Type="String",
))

SecretArnProd = t.add_parameter(Parameter(
    "SecretArnProd",
    Description="ARN for Secrets Manager secret for production",
    Type="String",
    Default="",
))

SecretsManagerKey = t.add_parameter(Parameter(
    "SecretsManagerKey",
    Description="KMS key for the use of secrets across accounts",
    Type="String",
))

t.add_condition("IsProdStage",
                Equals(Ref(Branch), "master")
                )

PipelineNotificationsTopic = t.add_resource(Topic(
    "PipelineNotificationsTopic",
    DisplayName=Sub("${AppName}-notifications-${AWS::Region}"),
    Condition="IsProdStage",
))

DynamicPipelineCleanupDev = t.add_resource(CustomResource(
    "DynamicPipelineCleanupDev",
    ServiceToken=Ref(DynamicPipelineCleanupLambdaArn),
    RoleArn={
        "Fn::Sub": "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${DevAwsAccountId}-dev"},
    Region=Ref("AWS::Region"),
    StackName=If("IsProdStage", {"Fn::Sub": "${AppName}-dev"}, {"Fn::Sub": "${AppName}-dev-${Suffix}"}),
))

DynamicPipelineCleanupProd = t.add_resource(CustomResource(
    "DynamicPipelineCleanupProd",
    ServiceToken=Ref(DynamicPipelineCleanupLambdaArn),
    RoleArn={
        "Fn::Sub": "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${ProdAwsAccountId}-prod"},
    Region=Ref("AWS::Region"),
    StackName=Sub("${AppName}-prod"),
    Condition="IsProdStage",
))

Pipeline = t.add_resource(Pipeline(
    "Pipeline",
    RoleArn=Ref(PipelineServiceRoleArn),
    Stages=[Stages(
        **{
            "Name": "Source",
            "Actions":
                [
                    Actions(**{
                        "Name": "CodeCommitSourceAction",
                        "RunOrder": 1,
                        "ActionTypeId":
                            ActionTypeId(
                                **{
                                    "Category": "Source",
                                    "Provider": "CodeCommit",
                                    "Owner": "AWS",
                                    "Version": "1"
                                }
                            ),
                        "OutputArtifacts":
                            [
                                OutputArtifacts(**{"Name": "Source"})
                            ],
                        "Configuration": ConfigurationProperties(
                            **{
                                "RepositoryName": Ref(AppName),
                                "BranchName": Ref(Branch)
                            }
                        )
                    })
                ]
        }),
        Stages({
            "Name":
                "Build",
            "Actions":
                [
                    Actions(**{
                        "Name":
                            "Build",
                        "RunOrder":
                            1,
                        "InputArtifacts":
                            [
                                InputArtifacts(**{
                                    "Name":
                                        "Source"
                                })
                            ],
                        "ActionTypeId":
                            ActionTypeId(**{
                                "Category":
                                    "Build",
                                "Provider":
                                    "CodeBuild",
                                "Owner":
                                    "AWS",
                                "Version":
                                    "1"
                            }),
                        "Configuration":
                            ConfigurationProperties(**{
                                "ProjectName":
                                    Ref("BuildProject")
                            }),
                        "OutputArtifacts":
                            [
                                OutputArtifacts(**{
                                    "Name":
                                        "BuildArtifact"
                                })
                            ]
                    })
                ]
        }), {"Name": "DeployToDev", "Actions": [
            {"Name": "CreateChangeSet", "RunOrder": 1, "InputArtifacts": [{"Name": "BuildArtifact"}],
             "ActionTypeId": {"Category": "Deploy", "Provider": "CloudFormation", "Owner": "AWS", "Version": "1"},
             "Configuration": {"ActionMode": "CHANGE_SET_REPLACE", "Capabilities": "CAPABILITY_IAM",
                               "ChangeSetName": {"Fn::Sub": "${AppName}-change-set-${Suffix}"}, "RoleArn": {
                     "Fn::Sub": "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${DevAwsAccountId}-dev"},
                               "StackName": If("IsProdStage", {"Fn::Sub": "${AppName}-dev"},
                                               {"Fn::Sub": "${AppName}-dev-${Suffix}"}),
                               "TemplatePath": "BuildArtifact::sample-transformed.yaml",
                               "TemplateConfiguration": "BuildArtifact::sample-configuration-dev.json"}, "RoleArn": {
                "Fn::Sub": "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${DevAwsAccountId}-dev"}},
            {"Name": "DeployChangeSet", "RunOrder": 2,
             "ActionTypeId": {"Category": "Deploy", "Provider": "CloudFormation", "Owner": "AWS", "Version": "1"},
             "Configuration": {"ActionMode": "CHANGE_SET_EXECUTE", "Capabilities": "CAPABILITY_IAM",
                               "ChangeSetName": {"Fn::Sub": "${AppName}-change-set-${Suffix}"}, "RoleArn": {
                     "Fn::Sub": "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${DevAwsAccountId}-dev"},
                               "StackName": If("IsProdStage", {"Fn::Sub": "${AppName}-dev"},
                                               {"Fn::Sub": "${AppName}-dev-${Suffix}"})}, "RoleArn": {
                "Fn::Sub": "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${DevAwsAccountId}-dev"}},
            {"Name": "SmokeTest", "RunOrder": 4, "InputArtifacts": [{"Name": "Source"}],
             "ActionTypeId": {"Category": "Build", "Provider": "CodeBuild", "Owner": "AWS", "Version": "1"},
             "Configuration": {"ProjectName": Ref("SmokeTestDevProject")}}]}, If("IsProdStage", {"Name": "DeployToProd",
                                                                                                 "Actions": [{
                                                                                                                 "Name": "CreateChangeSet",
                                                                                                                 "RunOrder": 1,
                                                                                                                 "InputArtifacts": [
                                                                                                                     {
                                                                                                                         "Name": "BuildArtifact"}],
                                                                                                                 "ActionTypeId": {
                                                                                                                     "Category": "Deploy",
                                                                                                                     "Provider": "CloudFormation",
                                                                                                                     "Owner": "AWS",
                                                                                                                     "Version": "1"},
                                                                                                                 "Configuration": {
                                                                                                                     "ActionMode": "CHANGE_SET_REPLACE",
                                                                                                                     "Capabilities": "CAPABILITY_IAM",
                                                                                                                     "ChangeSetName": {
                                                                                                                         "Fn::Sub": "${AppName}-change-set"},
                                                                                                                     "RoleArn": {
                                                                                                                         "Fn::Sub": "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${ProdAwsAccountId}-prod"},
                                                                                                                     "StackName": {
                                                                                                                         "Fn::Sub": "${AppName}-prod"},
                                                                                                                     "TemplatePath": "BuildArtifact::sample-transformed.yaml",
                                                                                                                     "TemplateConfiguration": "BuildArtifact::sample-configuration-prod.json"},
                                                                                                                 "RoleArn": {
                                                                                                                     "Fn::Sub": "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${ProdAwsAccountId}-prod"}},
                                                                                                             {
                                                                                                                 "Name": "Approval",
                                                                                                                 "RunOrder": 2,
                                                                                                                 "ActionTypeId": {
                                                                                                                     "Category": "Approval",
                                                                                                                     "Provider": "Manual",
                                                                                                                     "Owner": "AWS",
                                                                                                                     "Version": "1"},
                                                                                                                 "Configuration": {
                                                                                                                     "NotificationArn": Ref(
                                                                                                                         PipelineNotificationsTopic)}},
                                                                                                             {
                                                                                                                 "Name": "DeployChangeSet",
                                                                                                                 "RunOrder": 3,
                                                                                                                 "ActionTypeId": {
                                                                                                                     "Category": "Deploy",
                                                                                                                     "Provider": "CloudFormation",
                                                                                                                     "Owner": "AWS",
                                                                                                                     "Version": "1"},
                                                                                                                 "Configuration": {
                                                                                                                     "ActionMode": "CHANGE_SET_EXECUTE",
                                                                                                                     "Capabilities": "CAPABILITY_IAM",
                                                                                                                     "ChangeSetName": {
                                                                                                                         "Fn::Sub": "${AppName}-change-set"},
                                                                                                                     "RoleArn": {
                                                                                                                         "Fn::Sub": "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${ProdAwsAccountId}-prod"},
                                                                                                                     "StackName": {
                                                                                                                         "Fn::Sub": "${AppName}-prod"}},
                                                                                                                 "RoleArn": {
                                                                                                                     "Fn::Sub": "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${ProdAwsAccountId}-prod"}},
                                                                                                             {
                                                                                                                 "Name": "SmokeTest",
                                                                                                                 "RunOrder": 5,
                                                                                                                 "InputArtifacts": [
                                                                                                                     {
                                                                                                                         "Name": "Source"}],
                                                                                                                 "ActionTypeId": {
                                                                                                                     "Category": "Build",
                                                                                                                     "Provider": "CodeBuild",
                                                                                                                     "Owner": "AWS",
                                                                                                                     "Version": "1"},
                                                                                                                 "Configuration": {
                                                                                                                     "ProjectName": Ref(
                                                                                                                         "SmokeTestProdProject")}}]},
                                                                                 Ref("AWS::NoValue"))],
    ArtifactStore={"Type": "S3", "Location": Ref(ArtifactBucket),
                   "EncryptionKey": {"Id": Ref(ArtifactBucketKeyArn), "Type": "KMS"}},
))

BuildProject = t.add_resource(Project(
    "BuildProject",
    Artifacts={"Type": "CODEPIPELINE"},
    Source={"Type": "CODEPIPELINE", "BuildSpec": "buildspec.build.yaml"},
    Environment={"ComputeType": "BUILD_GENERAL1_SMALL", "Type": "LINUX_CONTAINER", "Image": Ref(BuildImageName),
                 "EnvironmentVariables": [{"Name": "AWS_ACCOUNT_ID", "Value": Ref("AWS::AccountId")},
                                          {"Name": "SAM_BUCKET", "Value": Ref(SamTranslationBucket)},
                                          {"Name": "SECRET_ARN_DEV", "Value": Ref(SecretArnDev)},
                                          {"Name": "SECRET_ARN_PROD", "Value": Ref(SecretArnProd)},
                                          {"Name": "SECRET_MANAGER_KEY", "Value": Ref(SecretsManagerKey)}]},
    ServiceRole=Ref(PipelineServiceRoleArn),
    EncryptionKey=Ref(ArtifactBucketKeyArn),
))

SmokeTestDevProject = t.add_resource(Project(
    "SmokeTestDevProject",
    Artifacts={"Type": "CODEPIPELINE"},
    Source={"Type": "CODEPIPELINE", "BuildSpec": "buildspec.smoketest.yaml"},
    Environment={"ComputeType": "BUILD_GENERAL1_SMALL", "Type": "LINUX_CONTAINER", "Image": Ref(BuildImageName),
                 "EnvironmentVariables": [{"Name": "STACK_NAME", "Type": "PLAINTEXT",
                                           "Value": If("IsProdStage", {"Fn::Sub": "${AppName}-dev"},
                                                       {"Fn::Sub": "${AppName}-dev-${Suffix}"})},
                                          {"Name": "ROLE_ARN", "Type": "PLAINTEXT", "Value": {
                                              "Fn::Sub": "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${DevAwsAccountId}-dev"}}]},
    ServiceRole=Ref(PipelineServiceRoleArn),
))

SmokeTestProdProject = t.add_resource(Project(
    "SmokeTestProdProject",
    Artifacts={"Type": "CODEPIPELINE"},
    Source={"Type": "CODEPIPELINE", "BuildSpec": "buildspec.smoketest.yaml"},
    Environment={"ComputeType": "BUILD_GENERAL1_SMALL", "Type": "LINUX_CONTAINER", "Image": Ref(BuildImageName),
                 "EnvironmentVariables": [
                     {"Name": "STACK_NAME", "Type": "PLAINTEXT", "Value": {"Fn::Sub": "${AppName}-prod"}},
                     {"Name": "ROLE_ARN", "Type": "PLAINTEXT", "Value": {
                         "Fn::Sub": "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${ProdAwsAccountId}-prod"}}]},
    ServiceRole=Ref(PipelineServiceRoleArn),
    Condition="IsProdStage",
))

PipelineNotificationTopic = t.add_output(Output(
    "PipelineNotificationTopic",
    Condition="IsProdStage",
    Description="Notification SNS ARN for shared pipeline notificiations",
    Value=Ref(PipelineNotificationsTopic),
    Export={"Name": {"Fn::Sub": "${AWS::StackName}-PipelineNotificationTopic"}},
))

PipelineNotificationTopicName = t.add_output(Output(
    "PipelineNotificationTopicName",
    Condition="IsProdStage",
    Description="Repo activity notifications topic name",
    Value=GetAtt(PipelineNotificationsTopic, "TopicName"),
    Export={"Name": {"Fn::Sub": "${AWS::StackName}-PipelineNotificationTopicName"}},
))

DevAccountId = t.add_output(Output(
    "DevAccountId",
    Condition="IsProdStage",
    Description="AWS account ID for dev that was passed in as a parameter",
    Value=Ref(DevAwsAccountId),
    Export={"Name": {"Fn::Sub": "${AppName}-DevAwsAccountId"}},
))

ProdAccountId = t.add_output(Output(
    "ProdAccountId",
    Condition="IsProdStage",
    Description="AWS account ID for prod that was passed in as a parameter",
    Value=Ref(ProdAwsAccountId),
    Export={"Name": {"Fn::Sub": "${AppName}-ProdAwsAccountId"}},
))

print(t.to_yaml())
