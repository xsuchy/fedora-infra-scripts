#! /usr/bin/python3

"""
Script producing data in https://copr-be-dev.cloud.fedoraproject.org/infra-stats/
"""
import json
import logging
import os
import shlex
import sys
import tempfile

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import backoff

LOG = logging.getLogger()

def retry_decorator(max_retries=60, max_time=60):
    """
    Retry AWS API query
    """
    return backoff.on_exception(
        backoff.expo,
        (BotoCoreError, ClientError),
        max_tries=max_retries,
        max_time=max_time,
        jitter=backoff.full_jitter,
    )

@retry_decorator()
def describe_regions_with_retry():
    """
    Get list of AWS regions
    """
    try:
        ec2 = boto3.client('ec2')
        return ec2.describe_regions()['Regions']
    except (BotoCoreError, ClientError) as err:
        print(f"An error occurred while describing regions: {err}")
        raise  # Raise the exception to trigger a retry

@retry_decorator()
def describe_instance_types(region_name, instance_types):
    """
    Get list of instances in given region
    """
    try:
        ec2_region = boto3.client('ec2', region_name=region_name)
        return ec2_region.describe_instance_types(InstanceTypes=instance_types)
    except (BotoCoreError, ClientError) as err:
        print(f"An error occurred while describing instances in {region_name}: {err}")
        raise  # Raise the exception to trigger a retry

@retry_decorator()
def describe_instances_with_retry(region_name):
    """
    Get list of instances in given region
    """
    try:
        ec2_region = boto3.client('ec2', region_name=region_name)
        return ec2_region.describe_instances()
    except (BotoCoreError, ClientError) as err:
        print(f"An error occurred while describing instances in {region_name}: {err}")
        raise  # Raise the exception to trigger a retry


class Stats:
    """ Calculators. """
    def __init__(self, name, print_items=None):
        self.data = {}
        self.name = name
        self.print_items = print_items

    def add(self, key, size=1):
        """
        Append size to the KEY counter, create the counter if it doesn't exist.
        """
        if key not in self.data:
            self.data[key] = 0
        self.data[key] += size

    def _sorted_iterator(self):
        for key, value in sorted(self.data.items(), key=lambda item: -item[1]):
            yield key, value

    def print(self, log):
        """ self.print() but more compressed """
        log.info(" ".join([f"{shlex.quote(key)}={value}"
                           for key, value in self._sorted_iterator()]))


class Analyzer:
    """
    Helper class for analysing instances/volumes/etc.
    """

    resultdir = None

    def _get_file_logger(self, filename):
        logger = logging.getLogger(filename)
        level = logging.DEBUG
        logger.setLevel(level)
        handler = logging.FileHandler(os.path.join(self.resultdir, filename))
        handler.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger


    def __init__(self, resultdir):
        if os.access(resultdir, os.W_OK):
            self.resultdir = resultdir
        else:
            self.resultdir = tempfile.mkdtemp()
            LOG.warning("Can't write into %s, working with %s",
                        resultdir, self.resultdir)

        self.owners = Stats("owners")
        self.vcpus = Stats("vcpus")
        self.memory = Stats("memory")
        self.instance_types = Stats("type")
        self.instance_types_per_owner = Stats("type-per-owner")
        self.errored_instances = {}
        self.log_instance_types = self._get_file_logger("instance-types-in-time.log")
        self.log_instance_types_owners = self._get_file_logger("instance-types-per-owner-in-time.log")
        self.log_owners = self._get_file_logger("owners-in-time.log")
        self.log_cpu_usage = self._get_file_logger("vcpu-usage-in-time.log")
        self.log_mem_usage = self._get_file_logger("memory-usage-in-time.log")
        self.instance_type_description = {}


    def _error(self, instance, message):
        instance_id = instance["InstanceId"]
        self.errored_instances.setdefault(instance_id, {
            "errors": [],
            "metadata": instance,
        })
        errors = self.errored_instances[instance_id]["errors"]
        errors.append(message)

    def analyze_instance(self, instance, region):
        """
        Check one instance metadata
        """
        fedora_group = "N/A"
        name_tag = "N/A"
        state = instance["State"]["Name"]

        for tag in instance.get('Tags', []):
            key = tag["Key"]
            value = tag["Value"]


            if key.lower() == "name":
                if name_tag != "N/A":
                    logging.error("Changing Name from %s to %s",
                                  name_tag, value)
                name_tag = value

            if key.lower() == "fedoragroup":
                if fedora_group != "N/A":
                    msg = (
                        "Tag FedoraGroup specified multiple times, changing "
                        f"from {name_tag} to {value}"
                    )
                    self._error(instance, msg)
                fedora_group = value

        if fedora_group == "N/A":
            self._error(instance, "Instance has no FedroaGroup owner")

        # TODO: Name is very useful thing, but not mandatory raising this as
        # error would report too many errors.
        #elif name_tag == "N/A":
        #    self._error(instance, f"Instance owned by {fedora_group} has no name=")

        # backup for better error reporting
        instance["script_override_region"] = region
        instance["script_override_name"] = name_tag
        instance["script_override_group"] = fedora_group

        if state != "terminated":
            self.owners.add(fedora_group)
            itype = instance['InstanceType']
            self.instance_types.add(itype)
            self.instance_types_per_owner.add(f"{itype}/{fedora_group}")
            self.vcpus.add(fedora_group, size=instance['CpuOptions']['CoreCount'])
            memory = self.instance_type_description[instance['InstanceType']]["memory"]
            self.memory.add(fedora_group, size=memory)

    def get_instance_types_info(self, instances, region):
        instance_types = set()
        for instance in instances:
            itype = instance["InstanceType"]
            if itype in self.instance_type_description:
                continue
            instance_types.add(itype)

        if not instance_types:
            return

        types = list(instance_types)
        types_info = describe_instance_types(region, types)

        for type_info in types_info["InstanceTypes"]:
            itype = type_info["InstanceType"]
            self.instance_type_description[itype] = {
                "memory": float(type_info["MemoryInfo"]["SizeInMiB"]) / 1024
            }

    def run(self):
        """
        Start the analysys
        """
        # Describe regions with retry
        regions = describe_regions_with_retry()

        # Get a list of all AWS region names
        region_names = [region['RegionName'] for region in regions]

        # Loop through each region and list EC2 instances with retry
        for region in region_names:
            instances = describe_instances_with_retry(region)
            for reservation in instances['Reservations']:
                self.get_instance_types_info(reservation["Instances"], region)
                for instance in reservation['Instances']:
                    self.analyze_instance(instance, region)

        self.owners.print(self.log_owners)
        self.instance_types.print(self.log_instance_types)
        self.instance_types_per_owner.print(self.log_instance_types_owners)
        self.vcpus.print(self.log_cpu_usage)
        self.memory.print(self.log_mem_usage)

        with open(os.path.join(self.resultdir, "last-run-errors.log"), "w", encoding="utf8") as file:
            output = {}
            for instance_id, data in self.errored_instances.items():
                metadata = data["metadata"]
                output_instance = output[instance_id] = {}
                output_instance["errors"] = data["errors"]
                output_instance["description"] = (
                    f"Instance owned by '{metadata['script_override_group']}' "
                    f"group, in region '{metadata['script_override_region']}', "
                    f"with name '{metadata['script_override_name']}'"
                )

            file.write(json.dumps(output, indent=4))


def _main():
    analyzer = Analyzer("/var/lib/copr/public_html/infra-stats/")
    try:
        analyzer.run()
    except Exception:  # pylint: disable=broad-exception-caught
        LOG.exception("Some exception happened")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(_main())
