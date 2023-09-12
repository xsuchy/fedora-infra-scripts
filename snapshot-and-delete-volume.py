#!/usr/bin/python

import boto3
import sys

def create_snapshot_with_tag(region, volume_id):
    # Initialize the EC2 client
    ec2_client = boto3.client('ec2', region_name=region)
    
    # Create the snapshot
    response = ec2_client.create_snapshot(
        VolumeId=volume_id,
        Description=f'GC - Snapshot of {volume_id}',
        TagSpecifications=[
            {
                'ResourceType': 'snapshot',
                'Tags': [
                    {
                        'Key': 'FedoraGroup',
                        'Value': 'garbage-collector'
                    }
                ]
            }
        ]
    )
    
    # Print out snapshot ID
    snapshot_id = response['SnapshotId']
    print(f"Created snapshot with ID: {snapshot_id}")

    # Delete the original volume after the snapshot is created
    ec2_client.delete_volume(VolumeId=volume_id)
    print(f"Deleted the original volume with ID: {volume_id}")

if len(sys.argv) != 3:
    print("Usage: python3 snapshot-and-delete-volume.py <region> <volume_id>")
    sys.exit(1)

region_name = sys.argv[1]
volume_id = sys.argv[2]

create_snapshot_with_tag(region_name, volume_id)
