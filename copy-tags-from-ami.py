#!/usr/bin/python3
"""
AI generated (and manually edited)
prompt:
You are AWS expert. Can you write Python script that goes over all
regions and in every region find all AMI that have tag "FedoraGroup" and if the
associated snapshot does not have this tag, then it will add the tag
"FedoraGroup" to the snapshot with the value that has the AMI?
"""

import boto3
import sys

def tag_snapshot_if_missing(ec2_client, snapshot_id, tag_key, tag_value):
    """
    Check if a snapshot has a given tag, and if not, tag it with the provided key and value.
    """
    try:
        # Retrieve the snapshot details
        response = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])
        snapshot = response['Snapshots'][0]
        existing_tags = {tag['Key']: tag['Value'] for tag in snapshot.get('Tags', [])}
        
        if tag_key not in existing_tags:
            print(f"Tagging snapshot {snapshot_id} with {tag_key}: {tag_value}")
            ec2_client.create_tags(
                Resources=[snapshot_id],
                Tags=[{'Key': tag_key, 'Value': tag_value}]
            )
        else:
            pass
            #print(f"Snapshot {snapshot_id} already has tag {tag_key} with value {existing_tags[tag_key]}")
    except Exception as e:
        print(f"Error processing snapshot {snapshot_id}: {e}")

def process_region(region):
    """
    For a given region, find AMIs with the tag 'FedoraGroup' and ensure that any associated
    EBS snapshot has the same tag.
    """
    print(f"\nProcessing region: {region}")
    ec2_client = boto3.client('ec2', region_name=region)

    try:
        # List AMIs owned by the account that have the FedoraGroup tag
        images_response = ec2_client.describe_images(
            Owners=['self'],
            Filters=[
                {
                    'Name': 'tag:FedoraGroup',
                    'Values': ['*']
                }
            ]
        )
    except Exception as e:
        print(f"Error describing images in region {region}: {e}")
        return

    for image in images_response.get('Images', []):
        image_id = image.get('ImageId')
        # Extract the FedoraGroup tag value from the AMI
        tag_value = None
        for tag in image.get('Tags', []):
            if tag['Key'] == 'FedoraGroup':
                tag_value = tag['Value']
                break

        if not tag_value:
            continue  # Skip if somehow the tag is missing

        print(f"Processing AMI {image_id} with FedoraGroup tag value: {tag_value}")

        # Iterate over the block device mappings to check for associated snapshots
        for mapping in image.get('BlockDeviceMappings', []):
            ebs = mapping.get('Ebs')
            if ebs and 'SnapshotId' in ebs:
                snapshot_id = ebs['SnapshotId']
                tag_snapshot_if_missing(ec2_client, snapshot_id, 'FedoraGroup', tag_value)

# Create a session and get all available regions for EC2
session = boto3.session.Session()
ec2_client = session.client('ec2')

try:
    regions_response = ec2_client.describe_regions()
except Exception as e:
    print(f"Error retrieving regions: {e}")
    sys.exit(1)

regions = [region['RegionName'] for region in regions_response['Regions']]

for region in regions:
    process_region(region)
