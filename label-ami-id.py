#!/usr/bin/python3

#ChatGPT prompt:
#You are a Python expert with experience in AWS. Can you write a script that gets the AMI id as an input, and it finds all AMIs of that id in all regions and add to these AMI a tag. The same for snapshots linked to these AMIs.

import argparse
import boto3

def tag_resource(resource_id, region, resource_type='ami', tags={'Key': 'ExampleKey', 'Value': 'ExampleValue'}):
    ec2 = boto3.client('ec2', region_name=region)
    response = ec2.create_tags(
        Resources=[resource_id],
        Tags=[tags]
    )
    print(f"Tagged {resource_type} {resource_id} in {region} with {tags}")

def find_and_tag_ami_and_snapshots(ami_id, tags):
    ec2 = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]

    for region in regions:
        ec2 = boto3.client('ec2', region_name=region)
        amis = ec2.describe_images(Filters=[{'Name': 'image-id', 'Values': [ami_id]}])
        
        for ami in amis['Images']:
            print(f"Found AMI {ami_id} in {region}")
            tag_resource(ami_id, region, 'ami', tags)
            
            # Tagging snapshots associated with the AMI
            for block_device in ami['BlockDeviceMappings']:
                if 'Ebs' in block_device:
                    snapshot_id = block_device['Ebs']['SnapshotId']
                    print(f"Found Snapshot {snapshot_id} for AMI {ami_id} in {region}")
                    tag_resource(snapshot_id, region, 'snapshot', tags)

parser = argparse.ArgumentParser(description='Tag AMIs and their snapshots based on AMI id substring.')
parser.add_argument('ami_id', type=str, help='AMI id to search for')

args = parser.parse_args()

ami_id = args.ami_id
tag_key = "FedoraGroup"
tag_value = "ga-archives"

tags = {'Key': tag_key, 'Value': tag_value}
find_and_tag_ami_and_snapshots(ami_id, tags)

