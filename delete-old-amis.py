#!/usr/bin/python3
# a script that goes over all regions and deletes all AMIs older than the specified date

import boto3
from datetime import datetime, timezone

def delete_old_amis(older_than_date):
    """
    Deletes all AMIs older than the specified date across all regions, excluding those with a 'FedoraGroup' tag.

    Parameters:
    older_than_date (datetime): The threshold date. AMIs created before this date will be deleted, unless they have a 'FedoraGroup' tag.
    """
    # Get a list of all regions
    ec2 = boto3.client('ec2', region_name='us-east-1')
    regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]
    
    for region in regions:
        print(f"Checking AMIs in region: {region}")
        ec2_region_client = boto3.client('ec2', region_name=region)
        
        # List all AMIs owned by the user
        my_amis = ec2_region_client.describe_images(Owners=['self'])['Images']
        
        # Filter AMIs created before the specified date
        old_amis = [ami for ami in my_amis if datetime.strptime(ami['CreationDate'], "%Y-%m-%dT%H:%M:%S.%f%z") < older_than_date]
        
        for ami in old_amis:
            ami_id = ami['ImageId']
            ami_name = ami.get('Name', '')
            # Check for 'FedoraGroup' tag
            has_fedora_group_tag = any(tag['Key'] == 'FedoraGroup' for tag in ami.get('Tags', []))
            
            if not has_fedora_group_tag:
                print(f"Deregistering AMI {ami_id} {ami_name} in region {region} as it does not have a 'FedoraGroup' tag")
                # Deregister the AMI
                ec2_region_client.deregister_image(ImageId=ami_id)
            else:
                pass
                #print(f"Skipping AMI {ami_id} in region {region} because it has a 'FedoraGroup' tag")
            
        print(f"Finished checking region: {region}")


# Specify the cutoff date in YYYY, MM, DD format
cutoff_date = datetime(2025, 10, 1, tzinfo=timezone.utc)
delete_old_amis(cutoff_date)
