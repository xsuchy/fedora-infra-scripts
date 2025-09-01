#!/usr/bin/python3
import awspricing
import boto3
import json
import progressbar

NOT_TAGGED = "Not tagged"
FEDORA_GROUP = "FedoraGroup"
SERVICE_NAME = "ServiceName"
HOURS_PER_MONTH = 730

RESERVED_INSTANCES = {
    # see https://docs.google.com/spreadsheets/d/1-5EyRjMSC2_LgHOpdG6_HwBjcSIY36rhYOLVYBcwAKY/edit?gid=0#gid=0
    'copr': {
      'us-east-1': {
        "t3a.medium": 2,
        "t3a.xlarge": 1,
        "t3a.small": 1,
        "c7i.xlarge": 11,
        "c7a.4xlarge": 1,
        "t3a.2xlarge": 1,
        "r5a.large": 1,
        "m5a.4xlarge": 1,
        "c7i.xlarge": 47,
        "c7g.xlarge": 39,
        "r7a.xlarge": 1,
}}}
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
            iops = volume.iops or 0
            tags = volume.tags or []
            
            (fedora_group, service_name) = parse_tags(tags)
            
            if fedora_group not in volume_data:
                volume_data[fedora_group] = {}
            
            if region not in volume_data[fedora_group]:
                volume_data[fedora_group][region] = {}
            if service_name not in volume_data[fedora_group][region]:
                volume_data[fedora_group][region][service_name] = {}

            if volume_type not in volume_data[fedora_group][region][service_name]:
                volume_data[fedora_group][region][service_name][volume_type] = [0, 0]
            
            volume_data[fedora_group][region][service_name][volume_type][0] += size
            volume_data[fedora_group][region][service_name][volume_type][1] += iops
    
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
            if instance.state['Name'] in ['terminated', 'stopped']:
                continue
            instance_type = instance.instance_type  # type of the instance
            if instance.spot_instance_request_id:
                instance_type = f"{instance_type}_spot"
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


def get_current_spot_pricing(region):
    ec2_client = boto3.client('ec2')
    ec2_resource = boto3.resource('ec2', region_name=region)
    response = ec2_client.describe_spot_instance_requests()
    spot_instance_requests = response['SpotInstanceRequests']

    pricing = {}
    for instance_request in spot_instance_requests:
        if instance_request['State'] == 'active':
            instance = ec2_resource.Instance(instance_request['InstanceId'])

            pricing[instance_request['LaunchSpecification']['InstanceType']] = float(instance_request['SpotPrice'])

    return pricing

def print_volume_instance_data(volume_data, instances_data, amis_data, snapshots_data):
    global REGIONS
    global GROUPS
    global SERVICE
    print("Getting price data:")
    ec2_offer = awspricing.offer('AmazonEC2')
    output_per_group = {}
    price_per_group = {}
    spot_pricing = {}
    for group in GROUPS:
        #import pdb; pdb.set_trace()
        output = ""
        price_group_total = 0
        for region in REGIONS:
            service_output = ""
            if region not in spot_pricing:
                spot_pricing[region] = get_current_spot_pricing(region)
                print(spot_pricing)
            for service in SERVICE:
                price_total = 0
                output_instance = []
                try:
                    for instance_type, count in instances_data[group][region][service].items():
                        try:
                            if RESERVED_INSTANCES[group][region][instance_type] > 0:
                                count_remaining = count - RESERVED_INSTANCES[group][region][instance_type]
                                if count_remaining <= 0:
                                    # do not count price of this instance
                                    output_instance += [f"        Instance Type: {instance_type} - Count: {count} - Price: 0 (reserved)"]
                                    continue
                                else:
                                    output_instance += [f"        Instance Type: {instance_type} - Count: {RESERVED_INSTANCES[group][region][instance_type]} - Price: 0 (reserved)"]
                                count = count_remaining
                        except KeyError:
                            pass
                        try:
                            if instance_type.endswith("_spot"):
                                price = spot_pricing[region][instance_type[:-5]]
                            else:
                                price = ec2_offer.ondemand_hourly(instance_type=instance_type,
                                                              region=region,
                                                              operating_system='Linux',
                                                             )
                        except (ValueError, AttributeError):
                            price = 0
                        price = round(price * HOURS_PER_MONTH * count)
                        price_total += price
                        output_instance += [f"        Instance Type: {instance_type} - Count: {count} - Price: ${price}"]
                except KeyError:
                    pass
                output_volume = []
                try:
                    for volume_type, size_iops in volume_data[group][region][service].items():
                        (size, iops) = size_iops
                        try:
                            price = ec2_offer.ebs_volume_monthly(volume_type=volume_type,
                                                                 region=region
                                                                )
                        except ValueError:
                            price = 0
                        iops_price = ec2_offer.ebs_iops_monthly(volume_type=volume_type,
                                                                region=region
                                                                )
                        price = round(price * size + iops_price*iops)
                        price_total += price
                        output_volume += [f"        Volume Type: {volume_type} - Total Size: {size} GiB - Price: ${price}"]
                except KeyError:
                    pass
                output_amis = ""
                try:
                    output_amis = f"        # of AMIs: {amis_data[group][region][service]}"
                except KeyError:
                    pass
                output_snapshots = ""
                if group in snapshots_data and region in snapshots_data[group] and service in snapshots_data[group][region]:
                    price = ec2_offer.ebs_snapshot_monthly(region=region, archive=True)
                    size = snapshots_data[group][region][service]['size']
                    price = round(price * size)
                    price_total += price
                    output_snapshots = f"        Snapshots: {size} GB in {snapshots_data[group][region][service]['count']} snapshots - Price ${price}"

                if output_instance or output_volume or output_amis or output_snapshots:
                    if service != NOT_TAGGED:
                        service_output += f"    Service Name: {service} - PriceSum: ${price_total}\n"
                    else:
                        service_output += f"    Service Name: N/A - PriceSum: ${price_total}\n"
                    if output_instance:
                        service_output += '\n'.join(output_instance) + "\n"
                    if output_volume:
                        service_output += '\n'.join(output_volume) + "\n"
                    if output_amis:
                        service_output += output_amis + "\n"
                    if output_snapshots:
                        service_output += output_snapshots + "\n"
                price_group_total += price_total
            if service_output:
                output += f"  Region: {region}\n"
                output += service_output.rstrip() + "\n"
        output_per_group[group] = f"{FEDORA_GROUP}: {group} - PriceSum: ${price_group_total}\n{output}\n"
        price_per_group[group] = price_group_total
    sorted_groups = sorted(output_per_group, key=lambda group: price_per_group[group], reverse=True)
    print("Summary:")
    for i in sorted_groups:
        print(f"  * {i} - ${price_per_group[i]}")
    print()
    for i in sorted_groups:
        print(output_per_group[i])
        print()


volume_data = get_volumes_by_group()
#volume_data = {}
instances_data = get_instances_by_group_and_region()
#instances_data = {}
amis_data = get_amis_by_group()
#amis_data = {}
snapshots_data = get_snapshots_by_group()
#snapshots_data = {}
print_volume_instance_data(volume_data, instances_data, amis_data, snapshots_data)
