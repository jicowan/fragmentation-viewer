#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#

import logging
import os
from ipaddress import ip_network
from collections import defaultdict

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from dotenv import load_dotenv

from vpc_data import (
    DEFAULT_REGION,
    get_ec2_client,
    get_all_eni_ips,
    get_instance_tags,
    resolve_tag_for_ip,
    calculate_fragmentation,
    list_regions,
    list_vpcs,
    get_vpc_subnets,
    get_subnet_ip_map,
)

load_dotenv()

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_region_from_request():
    """Extract region from request query parameters or headers"""
    return request.args.get('region') or request.headers.get('X-AWS-Region') or DEFAULT_REGION


@app.route('/')
def serve():
    """Serve the React app"""
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except:
        return jsonify({
            'message': 'Frontend not built yet. Run the Flask API on port 5000 and React dev server on port 3000'
        })


@app.route('/api/regions')
def get_regions():
    """Get all available AWS regions"""
    try:
        return jsonify(list_regions())
    except Exception as e:
        logger.error(f"Error fetching regions: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vpcs')
def get_vpcs():
    """Get all VPCs in the account for the specified region"""
    try:
        region = get_region_from_request()
        return jsonify(list_vpcs(region))
    except Exception as e:
        logger.error(f"Error fetching VPCs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vpc/<vpc_id>/subnets')
def get_subnets(vpc_id):
    """Get all subnets for a VPC with usage statistics"""
    try:
        region = get_region_from_request()
        return jsonify(get_vpc_subnets(vpc_id, region))
    except Exception as e:
        logger.error(f"Error fetching subnets: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subnet/<subnet_id>/ips')
def get_subnet_ips(subnet_id):
    """Get detailed IP allocation map for a subnet"""
    try:
        region = get_region_from_request()
        return jsonify(get_subnet_ip_map(subnet_id, region))
    except Exception as e:
        logger.error(f"Error fetching subnet IPs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vpc/<vpc_id>/tags')
def get_vpc_tags(vpc_id):
    """Discover all unique tag keys across ENIs, instances, subnets, and the VPC."""
    try:
        region = get_region_from_request()
        ec2_client = get_ec2_client(region)

        # Fetch the VPC to get its tags
        vpc_response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        vpc = vpc_response['Vpcs'][0]
        vpc_tag_keys = {tag['Key'] for tag in vpc.get('Tags', [])}

        # Fetch subnets and their tags
        subnet_paginator = ec2_client.get_paginator('describe_subnets')
        subnets_list = []
        for page in subnet_paginator.paginate(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]):
            subnets_list.extend(page['Subnets'])
        subnet_tag_keys = set()
        for subnet in subnets_list:
            for tag in subnet.get('Tags', []):
                subnet_tag_keys.add(tag['Key'])

        # Fetch ENIs and their tags
        eni_paginator = ec2_client.get_paginator('describe_network_interfaces')
        enis = []
        for page in eni_paginator.paginate(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]):
            enis.extend(page['NetworkInterfaces'])
        eni_tag_keys = set()
        for eni in enis:
            for tag in eni.get('TagSet', []):
                eni_tag_keys.add(tag['Key'])

        # Fetch instance tags
        instance_tags = get_instance_tags(ec2_client, vpc_id)
        instance_tag_keys = set()
        for tags in instance_tags.values():
            instance_tag_keys.update(tags.keys())

        # Build result: for each unique tag key, record which sources have it and count resources
        all_keys = vpc_tag_keys | subnet_tag_keys | eni_tag_keys | instance_tag_keys
        result = []
        for key in all_keys:
            sources = []
            resource_count = 0
            if key in eni_tag_keys:
                sources.append('eni')
                resource_count += sum(
                    1 for eni in enis
                    if any(t['Key'] == key for t in eni.get('TagSet', []))
                )
            if key in instance_tag_keys:
                sources.append('instance')
                resource_count += sum(
                    1 for tags in instance_tags.values()
                    if key in tags
                )
            if key in subnet_tag_keys:
                sources.append('subnet')
                resource_count += sum(
                    1 for s in subnets_list
                    if any(t['Key'] == key for t in s.get('Tags', []))
                )
            if key in vpc_tag_keys:
                sources.append('vpc')
                resource_count += 1

            result.append({
                'key': key,
                'sources': sources,
                'resourceCount': resource_count
            })

        result.sort(key=lambda x: x['resourceCount'], reverse=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching VPC tags: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vpc/<vpc_id>/tag-groups')
def get_tag_groups(vpc_id):
    """Get IP utilization grouped by values of a specified tag key."""
    tag_key = request.args.get('tag_key')
    if not tag_key:
        return jsonify({'error': 'tag_key query parameter is required'}), 400

    try:
        region = get_region_from_request()
        ec2_client = get_ec2_client(region)

        # Fetch VPC for its tags
        vpc_response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        vpc = vpc_response['Vpcs'][0]
        vpc_tags = {tag['Key']: tag['Value'] for tag in vpc.get('Tags', [])}

        # Fetch subnets
        subnet_paginator = ec2_client.get_paginator('describe_subnets')
        subnets_list = []
        for page in subnet_paginator.paginate(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]):
            subnets_list.extend(page['Subnets'])
        subnet_tags = {}
        subnet_info = {}
        for subnet in subnets_list:
            sid = subnet['SubnetId']
            subnet_tags[sid] = {tag['Key']: tag['Value'] for tag in subnet.get('Tags', [])}
            subnet_info[sid] = {
                'cidr': subnet['CidrBlock'],
                'totalIps': ip_network(subnet['CidrBlock']).num_addresses,
                'availableIps': subnet['AvailableIpAddressCount']
            }

        # Fetch ENIs
        eni_paginator = ec2_client.get_paginator('describe_network_interfaces')
        enis = []
        for page in eni_paginator.paginate(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]):
            enis.extend(page['NetworkInterfaces'])

        # Fetch instance tags
        instance_tags = get_instance_tags(ec2_client, vpc_id)

        # Build a map: eni_id -> eni (for tag resolution)
        eni_map = {eni['NetworkInterfaceId']: eni for eni in enis}

        # Extract all IPs from ENIs
        subnet_ip_details = get_all_eni_ips(enis)

        # Group IPs by tag value
        # Structure: {tag_value: {subnet_id: [ip_strings]}}
        groups = defaultdict(lambda: defaultdict(list))
        # Track IP type counts per group
        group_type_counts = defaultdict(lambda: {'primary': 0, 'secondary': 0, 'prefix_delegation': 0})

        for subnet_id, ip_list in subnet_ip_details.items():
            for ip_info in ip_list:
                eni_id = ip_info.get('interfaceId')
                eni = eni_map.get(eni_id, {})
                tag_value = resolve_tag_for_ip(tag_key, eni, instance_tags, subnet_tags, vpc_tags)
                group_name = tag_value if tag_value is not None else 'Untagged'

                groups[group_name][subnet_id].append(ip_info['ip'])
                ip_type = ip_info.get('type', 'primary')
                if ip_type in group_type_counts[group_name]:
                    group_type_counts[group_name][ip_type] += 1

        # Calculate per-group stats
        vpc_total_ips = sum(info['totalIps'] for info in subnet_info.values())
        vpc_used_ips = sum(len(ips) for sid_ips in subnet_ip_details.values() for ips in [sid_ips])

        group_results = []
        for tag_value, subnet_ips in groups.items():
            total_ips_used = sum(len(ips) for ips in subnet_ips.values())
            subnet_ids = list(subnet_ips.keys())

            # Weighted-average fragmentation across subnets
            total_weight = 0
            weighted_frag_sum = 0
            combined_frag_details = {
                'num_gaps': 0,
                'avg_gap_size': 0,
                'largest_gap': 0,
                'usable_prefixes': 0
            }

            for sid, ips in subnet_ips.items():
                if sid not in subnet_info:
                    continue
                info = subnet_info[sid]
                frag_score, frag_details = calculate_fragmentation(
                    ips, info['totalIps'], info['availableIps']
                )
                weight = info['totalIps']
                weighted_frag_sum += frag_score * weight
                total_weight += weight
                combined_frag_details['num_gaps'] += frag_details.get('num_gaps', 0)
                combined_frag_details['usable_prefixes'] += frag_details.get('usable_prefixes', 0)
                combined_frag_details['largest_gap'] = max(
                    combined_frag_details['largest_gap'],
                    frag_details.get('largest_gap', 0)
                )

            avg_frag = round(weighted_frag_sum / total_weight, 2) if total_weight > 0 else 0

            utilization_percent = round(
                (total_ips_used / vpc_used_ips) * 100, 2
            ) if vpc_used_ips > 0 else 0

            type_counts = group_type_counts[tag_value]
            group_results.append({
                'tagValue': tag_value,
                'totalIpsUsed': total_ips_used,
                'primaryIps': type_counts['primary'],
                'secondaryIps': type_counts['secondary'],
                'prefixDelegationIps': type_counts['prefix_delegation'],
                'subnetCount': len(subnet_ids),
                'subnetIds': subnet_ids,
                'utilizationPercent': utilization_percent,
                'fragmentationScore': avg_frag,
                'fragmentationDetails': combined_frag_details
            })

        group_results.sort(key=lambda x: x['totalIpsUsed'], reverse=True)

        return jsonify({
            'tagKey': tag_key,
            'groups': group_results,
            'vpcTotalIps': vpc_total_ips,
            'vpcUsedIps': vpc_used_ips
        })
    except Exception as e:
        logger.error(f"Error fetching tag groups: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'vpc-ip-fragmentation-viewer'})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
