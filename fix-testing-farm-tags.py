#!/usr/bin/python3

"""
Created using Gemini AI with prompt:

You are a Python and AWS expert. Can you write a Python script that for every region finds all instances that do not have "FedoraGroup" group tag, but have a tag "k8s.io/cluster-autoscaler/enabled" with value "true" and for these instances set a tag "FedoraGroup" to "CI" and set the same tag for volumes attached to these instances. 
"""

#!/usr/bin/env python3

"""
AWS Boto3 script to find and tag EC2 instances and their associated volumes.

This script performs the following actions for every AWS region:
1.  Finds all EC2 instances that:
    * Have a tag "k8s.io/cluster-autoscaler/enabled" with the value "true".
    * Do NOT have a tag with the key "FedoraGroup".
2.  For these matching instances, it adds the tag: "FedoraGroup" = "CI".
3.  For the volumes attached to these same instances, it also adds the tag:
    "FedoraGroup" = "CI".

PREREQUISITES:
1.  Boto3 library: `pip install boto3`
2.  AWS Credentials: Configure your credentials (e.g., via `aws configure`,
    environment variables, or an IAM role).

IAM PERMISSIONS REQUIRED:
* ec2:DescribeRegions
* ec2:DescribeInstances
* ec2:CreateTags (on instances and volumes)
"""

import boto3
from botocore.exceptions import ClientError

# --- CONFIGURATION ---
# Set to False to apply tags.
# Set to True to only print what would be tagged.
DRY_RUN = False

TAG_TO_FIND_KEY = "k8s.io/cluster-autoscaler/enabled"
TAG_TO_FIND_VALUE = "true"
TAG_TO_EXCLUDE_KEY = "FedoraGroup"
TAG_TO_SET_KEY = "FedoraGroup"
TAG_TO_SET_VALUE = "CI"
# ---------------------


def get_all_regions(ec2_client):
    """Gets a list of all available EC2 regions."""
    try:
        regions = [
            region["RegionName"]
            for region in ec2_client.describe_regions()["Regions"]
        ]
        return regions
    except ClientError as e:
        print(f"Error getting regions: {e}")
        return []


def process_region(region_name):
    """
    Finds and tags resources in a specific region.
    """
    print(f"\n--- Processing Region: {region_name} ---")
    try:
        client = boto3.client("ec2", region_name=region_name)
        paginator = client.get_paginator("describe_instances")

        # Filter for instances that have the autoscaler tag
        instances_to_check = paginator.paginate(
            Filters=[
                {
                    "Name": f"tag:{TAG_TO_FIND_KEY}",
                    "Values": [TAG_TO_FIND_VALUE],
                },
                {"Name": "instance-state-name", "Values": ["running", "stopped"]},
            ]
        )

        instances_to_tag = []
        volumes_to_tag = set()  # Use a set to avoid duplicate volume IDs

        for page in instances_to_check:
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    tags = instance.get("Tags", [])
                    tag_keys = [tag["Key"] for tag in tags]

                    # Check if the exclude tag is NOT present
                    if TAG_TO_EXCLUDE_KEY not in tag_keys:
                        print(
                            f"  [MATCH] Instance {instance_id} matches criteria."
                        )
                        instances_to_tag.append(instance_id)

                        # Find its attached volumes
                        for mapping in instance.get("BlockDeviceMappings", []):
                            if "Ebs" in mapping:
                                volume_id = mapping["Ebs"]["VolumeId"]
                                print(
                                    f"    -> Found attached volume: {volume_id}"
                                )
                                volumes_to_tag.add(volume_id)
                    else:
                        print(
                            f"  [SKIP] Instance {instance_id} already has"
                            f" '{TAG_TO_EXCLUDE_KEY}' tag."
                        )

        # Convert set to list for Boto3
        volume_list_to_tag = list(volumes_to_tag)

        # Apply tags to instances
        if instances_to_tag:
            tag_resources(
                client,
                region_name,
                "Instances",
                instances_to_tag,
                TAG_TO_SET_KEY,
                TAG_TO_SET_VALUE,
            )
        else:
            print(f"  No instances to tag in {region_name}.")

        # Apply tags to volumes
        if volume_list_to_tag:
            tag_resources(
                client,
                region_name,
                "Volumes",
                volume_list_to_tag,
                TAG_TO_SET_KEY,
                TAG_TO_SET_VALUE,
            )
        else:
            print(f"  No new volumes to tag in {region_name}.")

    except ClientError as e:
        # Handle regions that might be disabled or inaccessible
        if e.response["Error"]["Code"] == "AuthFailure":
            print(f"  [WARN] Could not access region {region_name}. Skipping.")
        else:
            print(f"  [ERROR] An error occurred in {region_name}: {e}")


def tag_resources(client, region, res_type, res_ids, key, value):
    """
    Applies a tag to a list of resources.
    """
    action = "Would tag" if DRY_RUN else "Tagging"
    print(
        f"  [{action}] {len(res_ids)} {res_type} in {region}"
        f" with {key}={value}."
    )

    if not DRY_RUN:
        try:
            # Boto3 create_tags can tag many resources at once
            client.create_tags(
                Resources=res_ids, Tags=[{"Key": key, "Value": value}]
            )
            print(f"  [SUCCESS] Tagged {len(res_ids)} {res_type}.")
        except ClientError as e:
            print(f"  [ERROR] Failed to tag {res_type}: {e}")
    else:
        # In dry run, just print the first few IDs as a sample
        for res_id in res_ids[:5]:
            print(f"    - {res_id}")
        if len(res_ids) > 5:
            print(f"    - ... and {len(res_ids) - 5} more.")


def main():
    print("Starting script to tag k8s instances and volumes...")
    if DRY_RUN:
        print("=" * 30)
        print("  MODE: DRY RUN")
        print("  No changes will be made.")
        print("=" * 30)

    # Use a base client in a common region to get the list of all regions
    base_client = boto3.client("ec2", region_name="us-east-1")
    all_regions = get_all_regions(base_client)

    if not all_regions:
        print("Could not retrieve AWS regions. Exiting.")
        return

    print(f"Found {len(all_regions)} regions to check.")

    for region in all_regions:
        process_region(region)

    print("\nScript finished.")
    if DRY_RUN:
        print("To apply changes, set DRY_RUN = False in the script.")


if __name__ == "__main__":
    main()

