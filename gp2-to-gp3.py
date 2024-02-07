#!/usr/bin/python3

import boto3
import sys

# Create an EC2 client
ec2 = boto3.client('ec2')

# Get list of all available regions
regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]

for region in regions:
    print(region)
    ec2 = boto3.client('ec2', region_name=region)
    
    # Get list of all volumes in the region
    response = ec2.describe_volumes()

    # Filter volumes that are of type 'gp2'
    gp2_volumes = [volume for volume in response['Volumes'] if volume['VolumeType'] == 'gp2']

    if not gp2_volumes:
        continue

    #import pdb; pdb.set_trace()
    for volume in gp2_volumes:
        volume_id = volume['VolumeId']
        print(f'Migrating volume {volume_id} in region {region} from gp2 to gp3...')
        
        # Modify the volume type to 'gp3'
        ec2.modify_volume(VolumeId=volume_id, VolumeType='gp3')
        print(f'Volume {volume_id} in region {region} migrated to gp3')
    #sys.exit(1)    
