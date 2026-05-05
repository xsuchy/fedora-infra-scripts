#!/usr/bin/python3
"""
You are Python and AWS expert. Write a script that for every region of AWS find
all volumes that does not have tag FedoraGroup and if the instance where the
volume is attached has the tag FedoraGroup, then add this tag to volume too.
"""

import boto3
import logging

# Configure logging for clear output
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def sync_volume_tags():
    # Initialize base EC2 client to dynamically fetch all available regions
    ec2_base = boto3.client('ec2')
    
    try:
        regions_resp = ec2_base.describe_regions()
        regions = [region['RegionName'] for region in regions_resp['Regions']]
        regions.remove('me-south-1') 
    except Exception as e:
        logging.error(f"Failed to retrieve AWS regions: {e}")
        return

    target_tag_key = 'FedoraGroup'

    for region in regions:
        logging.info(f"--- Checking region: {region} ---")
        ec2 = boto3.client('ec2', region_name=region)

        # Step 1: Pre-fetch all instances in this region that have the 'FedoraGroup' tag
        # This prevents us from doing an API call per volume/instance later.
        instance_tag_map = {}
        try:
            instance_paginator = ec2.get_paginator('describe_instances')
            instance_iterator = instance_paginator.paginate(
                Filters=[{'Name': 'tag-key', 'Values': [target_tag_key]}]
            )

            for page in instance_iterator:
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        
                        # Extract the specific value of the target tag
                        for tag in instance.get('Tags', []):
                            if tag['Key'] == target_tag_key:
                                instance_tag_map[instance_id] = tag['Value']
                                break

        except Exception as e:
            logging.error(f"Error describing instances in {region}: {e}")
            continue

        # If no instances have the tag in this region, we can safely skip volume checks
        if not instance_tag_map:
            logging.info(f"No instances with '{target_tag_key}' tag found in {region}. Skipping.")
            continue

        # Step 2: Find all attached volumes and check their tags
        try:
            vol_paginator = ec2.get_paginator('describe_volumes')
            # Filter specifically for volumes currently attached to an instance
            vol_iterator = vol_paginator.paginate(
                Filters=[{'Name': 'attachment.status', 'Values': ['attached']}]
            )

            for page in vol_iterator:
                for volume in page['Volumes']:
                    vol_id = volume['VolumeId']

                    # Check if the volume ALREADY has the target tag
                    vol_has_tag = any(tag['Key'] == target_tag_key for tag in volume.get('Tags', []))
                    if vol_has_tag:
                        continue

                    # If missing the tag, check the instance(s) it is attached to
                    for attachment in volume.get('Attachments', []):
                        attached_instance_id = attachment.get('InstanceId')

                        # If the attached instance is in our map, it has the tag
                        if attached_instance_id in instance_tag_map:
                            tag_value_to_apply = instance_tag_map[attached_instance_id]

                            logging.info(f"Tagging Volume: {vol_id} (Attached to {attached_instance_id}) "
                                         f"with {target_tag_key}={tag_value_to_apply}")

                            # Apply the tag to the volume
                            ec2.create_tags(
                                Resources=[vol_id],
                                Tags=[
                                    {
                                        'Key': target_tag_key,
                                        'Value': tag_value_to_apply
                                    }
                                ]
                            )
                            # Tagging once is sufficient (handles multi-attach corner cases gracefully)
                            break

        except Exception as e:
            logging.error(f"Error processing volumes in {region}: {e}")

if __name__ == "__main__":
    sync_volume_tags()
