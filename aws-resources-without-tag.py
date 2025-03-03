#!/usr/bin/python3
import boto3
from datetime import datetime, timedelta

TAG_NAME="FedoraGroup"

def get_all_regions():
    client = boto3.client('ec2')
    regions = [region['RegionName'] for region in client.describe_regions()['Regions']]
    return regions

def get_tag(tags, value):
    for tag in tags or []:
        if tag['Key'] == value:
            return tag['Value']
    return 'N/A'

def get_instance_name(instance_id, region):
    ec2 = boto3.client('ec2', region_name=region)
    response = ec2.describe_instances(InstanceIds=[instance_id])
    instance = response['Reservations'][0]['Instances'][0]
    instance_name = ''
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            instance_name = tag['Value']
    return instance_name

def older_than_24_hours(timestamp):
    return timestamp < datetime.now(timestamp.tzinfo) - timedelta(days=1)

def get_untagged_resources(region):
    ec2 = boto3.resource('ec2', region_name=region)
    client = boto3.client('ec2', region_name=region)
    untagged_instances = []
    untagged_volumes = []
    untagged_amis = []
    untagged_snapshots = []
    for instance in ec2.instances.all():
        if older_than_24_hours(instance.launch_time) and TAG_NAME not in [tag['Key'] for tag in instance.tags or []]:
            instance_name = get_tag(instance.tags, "Name")
            instance_owner = get_tag(instance.tags, "Owner")
            untagged_instances.append((instance.id, instance_name, instance_owner))
    for volume in ec2.volumes.all():
        if older_than_24_hours(volume.create_time) and TAG_NAME not in [tag['Key'] for tag in volume.tags or []]:
            attachment = volume.attachments[0] if volume.attachments else {}
            attached_instance_id = attachment.get('InstanceId', 'N/A')
            attached_instance_name = get_instance_name(attached_instance_id, region) if attached_instance_id != 'N/A' else 'N/A'
            volume_owner = get_tag(volume.tags, "Owner")
            volume_name = get_tag(volume.tags, "Name")
            untagged_volumes.append((volume.id, attached_instance_name, volume_owner, volume_name))

    for ami in client.describe_images(Owners=['self'])['Images']:
        # Extract the tags for easier processing
        tags = {tag['Key']: tag['Value'] for tag in ami.get('Tags', [])}
        # Check if the AMI lacks the desired tag
        if TAG_NAME not in tags:
            ami_name = ami.get('Name', '')
            untagged_amis.append((ami['ImageId'], ami_name))

    for snapshot in ec2.snapshots.filter(OwnerIds=['self']):
        if older_than_24_hours(snapshot.start_time) and TAG_NAME not in [tag['Key'] for tag in snapshot.tags or []]:
            snapshot_name = get_tag(snapshot.tags, 'Name')
            snapshot_size = snapshot.volume_size
            untagged_snapshots.append((snapshot.id, snapshot_name, snapshot_size))

    return untagged_instances, untagged_volumes, untagged_amis, untagged_snapshots

for region in get_all_regions():
    print("\nRegion: {}".format(region))
    (untagged_instances, untagged_volumes, untagged_amis, untagged_snapshots) = get_untagged_resources(region)
    if untagged_instances:
        print("Instances: (name, id, owner)")
        for (id, name, owner) in untagged_instances:
            print("  * {} ({}, {})".format(name, id, owner))
    if untagged_volumes:
        print("Volumes - [id name (attached to instance, owner)]: ")
        for (id, instance_name, owner, name) in untagged_volumes:
            print("  * {} {} ({}, {})".format(id, name, instance_name, owner))
    if untagged_amis:
        print("AMIs - [id, name]:")
        for (id, name) in untagged_amis:
            print(f"  * {id} {name}")
#    if untagged_snapshots:
#        print(f"Snapshots: (id, name, size)")
#        for (id, snapshot_name, snapshot_size) in untagged_snapshots:
#            print(f"  * {id} {snapshot_name} {snapshot_size} GB")

