#!/usr/bin/python3
import boto3
TAG_NAME="FedoraGroup"

def get_all_regions():
    client = boto3.client('ec2')
    regions = [region['RegionName'] for region in client.describe_regions()['Regions']]
    return regions

def get_name_tag(tags):
    for tag in tags or []:
        if tag['Key'] == 'Name':
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

def get_untagged_resources(region):
    ec2 = boto3.resource('ec2', region_name=region)
    untagged_instances = []
    untagged_volumes = []
    for instance in ec2.instances.all():
        if TAG_NAME not in [tag['Key'] for tag in instance.tags or []]:
            instance_name = get_name_tag(instance.tags)
            untagged_instances.append((instance.id, instance_name))
    for volume in ec2.volumes.all():
        if TAG_NAME not in [tag['Key'] for tag in volume.tags or []]:
            attachment = volume.attachments[0] if volume.attachments else {}
            attached_instance_id = attachment.get('InstanceId', 'N/A')
            attached_instance_name = get_instance_name(attached_instance_id, region) if attached_instance_id != 'N/A' else 'N/A'
            untagged_volumes.append((volume.id, attached_instance_name))

    return untagged_instances, untagged_volumes

for region in get_all_regions():
    print("\nRegion: {}".format(region))
    (untagged_instances, untagged_volumes) = get_untagged_resources(region)
    if not untagged_instances and not untagged_volumes:
        continue
    print("Instances:")
    for (id, name) in untagged_instances:
        print(" * {} ({})".format(name, id))
    print("Volumes - [id (attached to instance)]: ")
    for (id, instance_name) in untagged_volumes:
        print(" * {} ({})".format(id, instance_name))
