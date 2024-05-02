#!/usr/bin/python3

import boto3
import json
import progressbar

NOT_TAGGED = "Not tagged"
FEDORA_GROUP = "FedoraGroup"
SERVICE_NAME = "ServiceName"

# Initialize a session using Amazon EC2
session = boto3.Session()
ec2_resource = session.resource('ec2')

def get_all_regions():
    client = boto3.client('ec2')
    regions = [region['RegionName'] for region in client.describe_regions()['Regions']]
    return regions

REGIONS = get_all_regions()
#REGIONS = ['us-east-1']
GROUPS = {NOT_TAGGED}
SERVICE = {NOT_TAGGED}

def parse_tags(tags):
    global SERVICE
    global GROUPS
    tags = {tag['Key']: tag['Value'] for tag in tags}
    # Check if the volume has the "FedoraGroup" tag
    fedora_group = NOT_TAGGED
    if FEDORA_GROUP in tags:
        fedora_group = tags[FEDORA_GROUP]
        if fedora_group not in GROUPS:
            GROUPS.add(fedora_group)

    service_name = NOT_TAGGED
    if SERVICE_NAME in tags:
        service_name = tags[SERVICE_NAME]
        if service_name not in SERVICE:
            SERVICE.add(service_name)

    return (fedora_group, service_name)

def get_volumes_by_group():
    volume_data = {}
    global REGIONS
    global GROUPS
    global SERVICE
    print("Gathering volumes:")
    for region in progressbar.progressbar(REGIONS):
        ec2_resource = boto3.resource('ec2', region_name=region)
        volumes = ec2_resource.volumes.all()

        for volume in volumes:
            size = volume.size  # size of the volume in GiB
            volume_type = volume.volume_type  # type of the volume
            tags = volume.tags or []
            
            (fedora_group, service_name) = parse_tags(tags)
            
            if fedora_group not in volume_data:
                volume_data[fedora_group] = {}
            
            if region not in volume_data[fedora_group]:
                volume_data[fedora_group][region] = {}
            if service_name not in volume_data[fedora_group][region]:
                volume_data[fedora_group][region][service_name] = {}

            if volume_type not in volume_data[fedora_group][region][service_name]:
                volume_data[fedora_group][region][service_name][volume_type] = 0
            
            volume_data[fedora_group][region][service_name][volume_type] += size
    
    return volume_data


def get_amis_by_group():
    amis_data = {}
    global REGIONS
    global GROUPS
    global SERVICE
    print("Gathering AMIs:")
    for region in progressbar.progressbar(REGIONS):
        ec2 = boto3.client('ec2', region_name=region)
        amis = ec2.describe_images(Owners=['self'])['Images']

        for ami in amis:
            (fedora_group, service_name) = parse_tags(ami.get('Tags', [])) 

            if fedora_group not in amis_data:
                amis_data[fedora_group] = {}

            if region not in amis_data[fedora_group]:
                amis_data[fedora_group][region] = {}

            if service_name not in amis_data[fedora_group][region]:
                amis_data[fedora_group][region][service_name] = 0

            amis_data[fedora_group][region][service_name] += 1

    return amis_data

def get_snapshots_by_group():
    snapshots_data = {}
    global REGIONS
    global GROUPS
    global SERVICE
    print("Gathering Snapshots:")
    for region in progressbar.progressbar(REGIONS):
        ec2 = boto3.resource('ec2', region_name=region)
        snapshots = ec2.snapshots.filter(OwnerIds=['self'])
        for snap in snapshots:
            (fedora_group, service_name) = parse_tags(snap.tags or [])

            if fedora_group not in snapshots_data:
                snapshots_data[fedora_group] = {}

            if region not in snapshots_data[fedora_group]:
                snapshots_data[fedora_group][region] = {}

            if service_name not in snapshots_data[fedora_group][region]:
                snapshots_data[fedora_group][region][service_name] = {'count': 0, 'size': 0}

            snapshots_data[fedora_group][region][service_name]['count'] += 1
            snapshots_data[fedora_group][region][service_name]['size'] += snap.volume_size

    return snapshots_data


def get_instance_price(instance_type, region='us-east-1', service_code='AmazonEC2', offer_code='AmazonEC2'):
    """
    Get the price per hour for a specific instance type.
    
    :param instance_type: The type of the instance e.g., 't2.micro'.
    :param region: The AWS region e.g., 'us-east-1'.
    :param service_code: The service code for EC2.
    :param offer_code: The offer code for On-Demand instances.
    :return: The price per hour for the specified instance type.
    """
    
    pricing_client = boto3.client('pricing', region_name='us-east-1')
    import pdb; pdb.set_trace()
    
    try:
        response = pricing_client.get_products(
            ServiceCode=service_code,
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Compute Instance'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'termType', 'Value': 'OnDemand'}
            ],
            MaxResults=1
        )
        
        price_dimensions = json.loads(response['PriceList'][0])['terms']['OnDemand']
        price_dimension = next(iter(price_dimensions.values()))['priceDimensions']
        price_per_hour = next(iter(price_dimension.values()))['pricePerUnit']['USD']
        
        return price_per_hour
    
    except (IndexError, KeyError):
        return None

def get_instances_by_group_and_region():
    global REGIONS
    global GROUPS
    global SERVICE
    instances_data = {}
    print("Gathering instances:")
    for region in progressbar.progressbar(REGIONS):
        ec2_resource = session.resource('ec2', region_name=region)
        instances = ec2_resource.instances.all()
        
        for instance in instances:
            instance_type = instance.instance_type  # type of the instance
            # Check if the instance has the "FedoraGroup" tag
            tags = instance.tags or []
            (fedora_group, service_name) = parse_tags(tags)

            if fedora_group not in instances_data:
                instances_data[fedora_group] = {}
            
            # Update the instances_data dictionary
            if region not in instances_data[fedora_group]:
                instances_data[fedora_group][region] = {}

            if service_name not in instances_data[fedora_group][region]:
                instances_data[fedora_group][region][service_name] = {}

            if instance_type not in instances_data[fedora_group][region][service_name]:
                instances_data[fedora_group][region][service_name][instance_type] = 0
            
            instances_data[fedora_group][region][service_name][instance_type] += 1

    return instances_data


def print_volume_instance_data(volume_data, instances_data, amis_data, snapshots_data):
    global REGIONS
    global GROUPS
    global SERVICE
    for group in GROUPS:
        print(f"{FEDORA_GROUP}: {group}")
        #import pdb; pdb.set_trace()
        for region in REGIONS:
            service_output = ""
            for service in SERVICE:
                output_instance = []
                try:
                    for instance_type, count in instances_data[group][region][service].items():
                        #price = get_instance_price(instance_type, region)
                        output_instance += [f"        Instance Type: {instance_type} - Count: {count}"]
                except KeyError:
                    pass
                output_volume = []
                try:
                    for volume_type, size in volume_data[group][region][service].items():
                        output_volume += [f"        Volume Type: {volume_type} - Total Size: {size} GiB"]
                except KeyError:
                    pass
                output_amis = ""
                try:
                    output_amis = f"        # of AMIs: {amis_data[group][region][service]}"
                except KeyError:
                    pass
                output_snapshots = ""
                if group in snapshots_data and region in snapshots_data[group] and service in snapshots_data[group][region]:
                    output_snapshots = f"        Snapshots: {snapshots_data[group][region][service]['size']} GB in {snapshots_data[group][region][service]['count']} snapshots"

                if output_instance or output_volume or output_amis or output_snapshots:
                    if service != NOT_TAGGED:
                        service_output += f"    Service Name: {service}\n"
                    else:
                        service_output += "    Service Name:\n"
                    if output_instance:
                        service_output += '\n'.join(output_instance) + "\n"
                    if output_volume:
                        service_output += '\n'.join(output_volume) + "\n"
                    if output_amis:
                        service_output += output_amis + "\n"
                    if output_snapshots:
                        service_output + output_snapshots + "\n"
            #import pdb; pdb.set_trace()
            if service_output:
                print(f"  Region: {region}")
                print(service_output.rstrip())
        print()


volume_data = get_volumes_by_group()
#volume_data = {}
instances_data = get_instances_by_group_and_region()
amis_data = get_amis_by_group()
#amis_data = {}
snapshots_data = get_snapshots_by_group()
#snapshots_data = {}
print_volume_instance_data(volume_data, instances_data, amis_data, snapshots_data)
