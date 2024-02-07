#!/usr/bin/python3
import boto3
import re
import sys

# Regular expression to match AMI names that should be deleted
ami_name_pattern = "^Fedora-AtomicHost-.*"

def get_regions():
    """Get a list of all AWS regions."""
    ec2 = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]
    return regions

def delete_matching_amis(region):
    """Delete AMIs matching the regex in the specified region."""
    ec2 = boto3.client('ec2', region_name=region)
    amis = ec2.describe_images(Owners=['self'])['Images']
    
    for ami in amis:
        ami_name = ami.get('Name', '')
        if re.match(ami_name_pattern, ami_name):
            try:
                print(f"  Deleting AMI {ami['ImageId']}({ami_name})...")
                ec2.deregister_image(ImageId=ami['ImageId'])
                print(f"    AMI {ami['ImageId']} deleted successfully.")
            except Exception as e:
                print(f"Error deleting AMI {ami['ImageId']}: {e}")

regions = get_regions()
for region in regions:
    print(f"Processing region {region}...")
    delete_matching_amis(region)
print("Completed processing all regions.")

