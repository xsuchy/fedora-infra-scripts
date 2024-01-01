#!/usr/bin/python3

import boto3
import json
import progressbar

# Initialize a session using Amazon EC2
session = boto3.Session()
ec2_resource = session.resource('ec2')

def get_all_regions():
    client = boto3.client('ec2')
    regions = [region['RegionName'] for region in client.describe_regions()['Regions']]
    return regions

REGIONS = get_all_regions()
GROUPS = set()

def get_volumes_by_group():
    volume_data = {}
    global REGIONS
    global GROUPS
    print("Gathering volumes:")
    for region in progressbar.progressbar(REGIONS):
        ec2_resource = boto3.resource('ec2', region_name=region)
        volumes = ec2_resource.volumes.all()

        for volume in volumes:
            size = volume.size  # size of the volume in GiB
            volume_type = volume.volume_type  # type of the volume
            
            # Check if the volume has the "FedoraGroup" tag
            fedora_group = None
            for tag in volume.tags or []:
                if tag['Key'] == 'FedoraGroup':
                    fedora_group = tag['Value']
                    GROUPS.add(fedora_group)
                    break
            
            if not fedora_group:
                continue  # skip volumes without "FedoraGroup" tag
            
            if fedora_group not in volume_data:
                volume_data[fedora_group] = {}
            
            if region not in volume_data[fedora_group]:
                volume_data[fedora_group][region] = {}

            if volume_type not in volume_data[fedora_group][region]:
                volume_data[fedora_group][region][volume_type] = 0
            
            volume_data[fedora_group][region][volume_type] += size
    
    return volume_data

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
    instances_data = {}
    print("Gathering instances:")
    for region in progressbar.progressbar(REGIONS):
        ec2_resource = session.resource('ec2', region_name=region)
        instances = ec2_resource.instances.all()
        
        for instance in instances:
            instance_type = instance.instance_type  # type of the instance
            # Check if the instance has the "FedoraGroup" tag
            fedora_group = None
            for tag in instance.tags or []:
                if tag['Key'] == 'FedoraGroup':
                    fedora_group = tag['Value']
                    GROUPS.add(fedora_group)
                    break

            if not fedora_group:
                continue  # skip instances without "FedoraGroup" tag

            if fedora_group not in instances_data:
                instances_data[fedora_group] = {}
            
            # Update the instances_data dictionary
            if region not in instances_data[fedora_group]:
                instances_data[fedora_group][region] = {}
                
            if instance_type not in instances_data[fedora_group][region]:
                instances_data[fedora_group][region][instance_type] = 0
            
            instances_data[fedora_group][region][instance_type] += 1

    return instances_data

def print_volume_instance_data(volume_data, instances_data):
    for group in GROUPS:
        print(f"FedoraGroup: {group}")
        for region in REGIONS:
            output_instance = []
            try:
                for instance_type, count in instances_data[group][region].items():
                    #price = get_instance_price(instance_type, region)
                    output_instance += [f"        Instance Type: {instance_type} - Count: {count}"]
            except KeyError:
                pass
            output_volume = []
            try:
                for volume_type, size in volume_data[group][region].items():
                    output_volume += [f"        Volume Type: {volume_type} - Total Size: {size} GiB"]
            except KeyError:
                pass

            if output_instance or output_volume:
                print(f"  Region: {region}")
                if output_instance:
                    print('\n'.join(output_instance))
                if output_volume:
                    print('\n'.join(output_volume))
        print()

volume_data = get_volumes_by_group()
instances_data = get_instances_by_group_and_region()
print_volume_instance_data(volume_data, instances_data)
