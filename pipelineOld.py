from troposphere import (
    Parameter,
    Ref,
    Template,
    Condition,
    Equals,
    And,
    Or,
    Not,
    If,
    Sub
)
from troposphere.codepipeline import (
    Pipeline,
    Stages,
    Actions,
    ActionTypeId,
    OutputArtifacts,
    InputArtifacts,
    ArtifactStore,
    DisableInboundStageTransitions
)
from troposphere.sns import (
    Topic
)

from troposphere.cloudformation import (
    CustomResource
)


t = Template()
t.set_version("2010-09-09")

t.set_description("""
  (qs-1ph8nehb7) 
  Serverless CICD Quick Start
  Codepipeline shared resources and security
""")

PipelineParam = {
    "AppName": t.add_parameter(
        Parameter(
            "AppName",
            Description="Application name, used for the repository and child stack name",
            Type="String",
            Default="Sample"
        )
    ),
    "BuildImageName": t.add_parameter(
        Parameter(
            "BuildImageName",
            Description="Docker image for application build",
            Type="String",
            Default="aws/codebuild/nodejs:10.1.0"
        )
    ),
    "DevAwsAccountId": t.add_parameter(
        Parameter(
            "DevAwsAccountId",
            Description="AWS account ID for development account",
            Type="String",
            AllowedPattern="(\\d{12}|^$)",
            ConstraintDescription="Must be an AWS account ID",
            Default="159527342995"

        )
    ),
    "ProdAwsAccountId": t.add_parameter(
        Parameter(
            "ProdAwsAccountId",
            Description="AWS account ID for production account",
            Type="String",
            AllowedPattern="(\\d{12}|^$)",
            ConstraintDescription="Must be an AWS account ID",
            Default="159527342995"
        )
    ),
    "Branch": t.add_parameter(
        Parameter(
            "Branch",
            Description="Repository branch name",
            Type="String",
            Default="master"
        )
    ),
    "Suffix": t.add_parameter(
        Parameter(
            "Suffix",
            Description="Repository branch name (adapted to use in CloudFormation stack name)",
            Type="String",
            Default="master"
        )
    ),
    "ArtifactBucket": t.add_parameter(
        Parameter(
            "ArtifactBucket",
            Description="Artifact S3 bucket",
            Type="String"
        )
    ),
    "ArtifactBucketKeyArn": t.add_parameter(
        Parameter(
            "ArtifactBucketKeyArn",
            Description="ARN of the artifact bucket KMS key",
            Type="String",
        )
    ),
    "PipelineServiceRoleArn": t.add_parameter(
        Parameter(
            "PipelineServiceRoleArn",
            Description="Pipeline service role ARN",
            Type="String"
        )
    ),
    "SamTranslationBucket": t.add_parameter(
        Parameter(
            "SamTranslationBucket",
            Description="S3 bucket for SAM translations",
            Type="String"
        )
    ),
    "DynamicPipelineCleanupLambdaArn": t.add_parameter(
        Parameter(
            "DynamicPipelineCleanupLambdaArn",
            Description="ARN of Lambda function to clean up dynamic pipeline",
            Type="String",
        )
    ),
    "SecretArnDev": t.add_parameter(
        Parameter(
            "SecretArnDev",
            Description="ARN for Secrets Manager secret for dev",
            Type="String",
        )
    ),
    "SecretArnProd": t.add_parameter(
        Parameter(
            "SecretArnProd",
            Description="ARN for Secrets Manager secret for production",
            Type="String",
            Default=""
        )
    ),
    "SecretsManagerKey": t.add_parameter(
        Parameter(
            "SecretsManagerKey",
            Description="KMS key for the use of secrets across accounts",
            Type="String"
        )
    ),
}

conditions = {
    "IsProdStage": Equals(
        Ref("Branch"),
        "master"
    )
}




resources = {
    "PipelineNotificationsTopic":
        Topic(
            "PipelineNotificationsTopic",
            Condition="IsProdStage",
            DisplayName=Sub("${AppName}-notifications-${AWS::Region}"),
        ),
    "DynamicPipelineCleanupDev":
        CustomResource(
            "DynamicPipelineCleanupDev",
            Version="1.0",
            ServiceToken=Ref("DynamicPipelineCleanupLambdaArn"),
            RoleArn=Sub("arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${"
                        "DevAwsAccountId}-dev"),
            Region=Ref("AWS::Region"),
            StackName=If("IsProdStage",
                         Sub("${AppName}-dev"),
                         Sub("${AppName}-dev-${Suffix}")
                         )
        ),

    "DynamicPipelineCleanupProd":
        CustomResource(
            "DynamicPipelineCleanupProd",
            Condition="IsProdStage",
            Version="1.0",
            ServiceToken=Ref("DynamicPipelineCleanupLambdaArn"),
            RoleArn=Sub("arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${"
                        "DevAwsAccountId}-dev"),
            Region=Ref("AWS::Region"),
            StackName=Sub("${AppName}-prod")
        ),
    "Pipeline":
        Pipeline(
            "Pipeline",
            RoleArn=Ref("PipelineServiceRoleArn"),
            Stages=[
                Stages(
                    Name="Source",
                    Actions=[
                        Actions(
                            Name="CodeCommitSourceAction",
                            RunOrder=1,
                            ActionTypeId=ActionTypeId(
                                Category="Source",
                                Provider="CodeCommit",
                                Owner="AWS",
                                Version='1'
                            )

                        )
                    ]
                )
            ]
        ),
    "Pipeline2":
    Pipeline(
        "Pipeline",
        RoleArn=Ref(PipelineServiceRoleArn),
        Stages=Stages(

            Actions=[
            Actions(
                **{"Name": "CodeCommitSourceAction",
                 "RunOrder": 1,
                 "ActionTypeId":
                     ActionTypeId(
                         **{"Category": "Source",
                            "Provider": "CodeCommit",
                            "Owner": "AWS",
                            "Version": "1"
                            }
                     ),
                 "OutputArtifacts":
                     OutputArtifacts(**{
                         "Name": "Source"
                     }),
                 "Configuration":
                     ConfigurationProperties(
                         **{
                             "RepositoryName": Ref(AppName),
                             "BranchName": Ref(Branch)
                         }
                     )
                 }
            ),
                Actions(
                    **{"Name": "Build",
                       "RunOrder": 1,
                       "InputArtifacts":
                           InputArtifacts(
                               **{"Name": "Source"}
                           ),
                       "ActionTypeId":
                           ActionTypeId(**
                                        {"Category": "Build",
                                         "Provider": "CodeBuild",
                                         "Owner": "AWS",
                                         "Version": "1"
                                         }),
             "Configuration":
                           ConfigurationProperties(
                               **{
                                   "ProjectName":
                                       Ref("BuildProject")
                               }
                           ),
             "OutputArtifacts":
                           OutputArtifacts(
                               **{
                                   "Name": "BuildArtifact"
                               }
                           )
                       }
                ),
                Actions(
                    **{"Name": "CreateChangeSet", "RunOrder": 1, "InputArtifacts": InputArtifacts(**{"Name": "BuildArtifact"}),
             "ActionTypeId": ActionTypeId(
                 **{"Category": "Deploy", "Provider": "CloudFormation", "Owner": "AWS", "Version": "1"}),
             "Configuration": ConfigurationProperties(
                 **{"ActionMode": "CHANGE_SET_REPLACE", "Capabilities": "CAPABILITY_IAM",
                    "ChangeSetName": Sub("${AppName}-change-set-${Suffix}"), "RoleArn": Sub(
                         "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${DevAwsAccountId}-dev"),
                    "StackName": If("IsProdStage", Sub("${AppName}-dev"), Sub("${AppName}-dev-${Suffix}")),
                    "TemplatePath": "BuildArtifact::sample-transformed.yaml",
                    "TemplateConfiguration": "BuildArtifact::sample-configuration-dev.json"}), "RoleArn": Sub(
                "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${DevAwsAccountId}-dev")},
            {"Name": "DeployChangeSet", "RunOrder": 2, "ActionTypeId": ActionTypeId(
                **{"Category": "Deploy", "Provider": "CloudFormation", "Owner": "AWS", "Version": "1"}),
             "Configuration": ConfigurationProperties(
                 **{"ActionMode": "CHANGE_SET_EXECUTE", "Capabilities": "CAPABILITY_IAM",
                    "ChangeSetName": Sub("${AppName}-change-set-${Suffix}"), "RoleArn": Sub(
                         "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${DevAwsAccountId}-dev"),
                    "StackName": If("IsProdStage", Sub("${AppName}-dev"), Sub("${AppName}-dev-${Suffix}"))}),
             "RoleArn": Sub(
                 "arn:aws:iam::${DevAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${DevAwsAccountId}-dev")},
            {"Name": "SmokeTest", "RunOrder": 4, "InputArtifacts": InputArtifacts(**{"Name": "Source"}),
             "ActionTypeId": ActionTypeId(**{"Category": "Build", "Provider": "CodeBuild", "Owner": "AWS", "Version": "1"}),
             "Configuration": ConfigurationProperties(**{"ProjectName": Ref("SmokeTestDevProject")})}), If("IsProdStage",
                                                                                                           Actions({
                                                                                                                       "Name": "CreateChangeSet",
                                                                                                                       "RunOrder": 1,
                                                                                                                       "InputArtifacts": InputArtifacts(
                                                                                                                           **{
                                                                                                                               "Name": "BuildArtifact"}),
                                                                                                                       "ActionTypeId": ActionTypeId(
                                                                                                                           **{
                                                                                                                               "Category": "Deploy",
                                                                                                                               "Provider": "CloudFormation",
                                                                                                                               "Owner": "AWS",
                                                                                                                               "Version": "1"}),
                                                                                                                       "Configuration": ConfigurationProperties(
                                                                                                                           **{
                                                                                                                               "ActionMode": "CHANGE_SET_REPLACE",
                                                                                                                               "Capabilities": "CAPABILITY_IAM",
                                                                                                                               "ChangeSetName": Sub(
                                                                                                                                   "${AppName}-change-set"),
                                                                                                                               "RoleArn": Sub(
                                                                                                                                   "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${ProdAwsAccountId}-prod"),
                                                                                                                               "StackName": Sub(
                                                                                                                                   "${AppName}-prod"),
                                                                                                                               "TemplatePath": "BuildArtifact::sample-transformed.yaml",
                                                                                                                               "TemplateConfiguration": "BuildArtifact::sample-configuration-prod.json"}),
                                                                                                                       "RoleArn": Sub(
                                                                                                                           "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${ProdAwsAccountId}-prod")},
                                                                                                                   {
                                                                                                                       "Name": "Approval",
                                                                                                                       "RunOrder": 2,
                                                                                                                       "ActionTypeId": ActionTypeId(
                                                                                                                           **{
                                                                                                                               "Category": "Approval",
                                                                                                                               "Provider": "Manual",
                                                                                                                               "Owner": "AWS",
                                                                                                                               "Version": "1"}),
                                                                                                                       "Configuration": ConfigurationProperties(
                                                                                                                           **{
                                                                                                                               "NotificationArn": Ref(
                                                                                                                                   PipelineNotificationsTopic)})},
                                                                                                                   {
                                                                                                                       "Name": "DeployChangeSet",
                                                                                                                       "RunOrder": 3,
                                                                                                                       "ActionTypeId": ActionTypeId(
                                                                                                                           **{
                                                                                                                               "Category": "Deploy",
                                                                                                                               "Provider": "CloudFormation",
                                                                                                                               "Owner": "AWS",
                                                                                                                               "Version": "1"}),
                                                                                                                       "Configuration": ConfigurationProperties(
                                                                                                                           **{
                                                                                                                               "ActionMode": "CHANGE_SET_EXECUTE",
                                                                                                                               "Capabilities": "CAPABILITY_IAM",
                                                                                                                               "ChangeSetName": Sub(
                                                                                                                                   "${AppName}-change-set"),
                                                                                                                               "RoleArn": Sub(
                                                                                                                                   "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineDeploymentRole-${AWS::Region}-${ProdAwsAccountId}-prod"),
                                                                                                                               "StackName": Sub(
                                                                                                                                   "${AppName}-prod")}),
                                                                                                                       "RoleArn": Sub(
                                                                                                                           "arn:aws:iam::${ProdAwsAccountId}:role/CodePipelineServiceRole-${AWS::Region}-${ProdAwsAccountId}-prod")},
                                                                                                                   {
                                                                                                                       "Name": "SmokeTest",
                                                                                                                       "RunOrder": 5,
                                                                                                                       "InputArtifacts": InputArtifacts(
                                                                                                                           **{
                                                                                                                               "Name": "Source"}),
                                                                                                                       "ActionTypeId": ActionTypeId(
                                                                                                                           **{
                                                                                                                               "Category": "Build",
                                                                                                                               "Provider": "CodeBuild",
                                                                                                                               "Owner": "AWS",
                                                                                                                               "Version": "1"}),
                                                                                                                       "Configuration": ConfigurationProperties(
                                                                                                                           **{
                                                                                                                               "ProjectName": Ref(
                                                                                                                                   "SmokeTestProdProject")})}),
                                                                                                           Ref(
                                                                                                               "AWS::NoValue"))],
        ArtifactStore={"Type": "S3", "Location": Ref(ArtifactBucket),
                       "EncryptionKey": {"Id": Ref(ArtifactBucketKeyArn), "Type": "KMS"}},
        )
    )

}


for c in conditions:
    t.add_condition(c, conditions[c])

for r in resources.values():
    t.add_resource(r)

print(t.to_yaml())
