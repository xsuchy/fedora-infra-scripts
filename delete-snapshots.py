#!/usr/bin/python3

import boto3
from botocore.exceptions import ClientError
import datetime
import sys

def delete_snapshots():
    # Get a list of all regions
    ec2 = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]

    # Define the cutoff date
    cutoff_date = datetime.datetime(2019, 1, 1)

    for region in regions:
        print(f"Checking region: {region}")
        ec2 = boto3.client('ec2', region_name=region)

        # Get all snapshots
        snapshots = ec2.describe_snapshots(OwnerIds=['self'])['Snapshots']

        for snapshot in snapshots:
            creation_date = datetime.datetime.strptime(snapshot['StartTime'].strftime("%Y-%m-%d"), "%Y-%m-%d")
            
            # Check if the snapshot has the required tag and is older than the cutoff date
            if creation_date < cutoff_date and not any(tag['Key'] == 'FedoraGroup' for tag in snapshot.get('Tags', [])):
                try:
                    ec2.delete_snapshot(SnapshotId=snapshot['SnapshotId'])
                    print(f"Deleted snapshot {snapshot['SnapshotId']} started at {creation_date}")
                except ClientError as e:
                    pass
                    #print(f"Error: {e}")

delete_snapshots()
