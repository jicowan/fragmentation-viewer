#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#

import logging
import os
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import boto3
from ipaddress import ip_network, ip_address
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
CORS(app)

# Default region
DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_ec2_client(region=None):
    """Get EC2 client for the specified region"""
    region = region or DEFAULT_REGION
    return boto3.client('ec2', region_name=region)


def get_region_from_request():
    """Extract region from request query parameters or headers"""
    return request.args.get('region') or request.headers.get('X-AWS-Region') or DEFAULT_REGION


def get_reserved_ips(cidr_block):
    """AWS reserves first 4 and last IP in each subnet"""
    network = ip_network(cidr_block)
    reserved = set()

    # First 4 IPs (.0, .1, .2, .3) and last IP (broadcast)
    reserved.add(str(network.network_address))
    reserved.add(str(network.network_address + 1))
    reserved.add(str(network.network_address + 2))
    reserved.add(str(network.network_address + 3))
    reserved.add(str(network.broadcast_address))

    return reserved


def get_subnet_cidr_reservations(ec2_client, subnet_id):
    """
    Get CIDR reservations for a subnet.
    Returns a dict mapping IP addresses to reservation details.
    """
    try:
        response = ec2_client.get_subnet_cidr_reservations(SubnetId=subnet_id)

        reservation_ips = {}
        for reservation in response.get('SubnetIpv4CidrReservations', []):
            cidr = reservation['Cidr']
            reservation_type = reservation['ReservationType']  # 'explicit' or 'prefix'
            description = reservation.get('Description', '')
            reservation_id = reservation['SubnetCidrReservationId']

            logger.info(f"Found CIDR reservation: {cidr} ({reservation_type}) - {description}")

            # Get all IPs in the reserved CIDR block
            try:
                reserved_network = ip_network(cidr)
                for ip in reserved_network:
                    reservation_ips[str(ip)] = {
                        'cidr': cidr,
                        'type': reservation_type,
                        'description': description,
                        'reservationId': reservation_id
                    }
            except Exception as e:
                logger.error(f"Error processing reservation CIDR {cidr}: {str(e)}")

        return reservation_ips
    except Exception as e:
        logger.error(f"Error fetching subnet CIDR reservations: {str(e)}")
        return {}


def get_all_eni_ips(enis):
    """
    Extract all IPs from ENIs including:
    - Primary private IPs
    - Secondary private IPs (used by EKS pods without dedicated ENIs)
    - IPs from IPv4 prefixes (prefix delegation for EKS)
    """
    subnet_ips = defaultdict(list)

    for eni in enis:
        subnet_id = eni['SubnetId']
        interface_id = eni['NetworkInterfaceId']
        description = eni.get('Description', '')

        # Get all private IP addresses (primary and secondary)
        for private_ip_info in eni.get('PrivateIpAddresses', []):
            ip = private_ip_info['PrivateIpAddress']
            subnet_ips[subnet_id].append({
                'ip': ip,
                'type': 'primary' if private_ip_info.get('Primary', False) else 'secondary',
                'status': eni['Status'],
                'description': description,
                'interfaceId': interface_id,
                'attachmentStatus': eni.get('Attachment', {}).get('Status', 'detached')
            })

        # Get IPs from IPv4 prefixes (EKS prefix delegation)
        for prefix in eni.get('Ipv4Prefixes', []):
            prefix_cidr = prefix['Ipv4Prefix']
            logger.info(f"Found IPv4 prefix: {prefix_cidr} on ENI {interface_id}")

            # Each prefix is typically a /28 (16 IPs) assigned to the ENI
            # Pods will use IPs from this prefix
            try:
                prefix_network = ip_network(prefix_cidr)
                for ip in prefix_network.hosts():
                    subnet_ips[subnet_id].append({
                        'ip': str(ip),
                        'type': 'prefix_delegation',
                        'status': 'prefix',
                        'description': f"{description} (Prefix: {prefix_cidr})",
                        'interfaceId': interface_id,
                        'attachmentStatus': 'prefix_assigned'
                    })
            except Exception as e:
                logger.error(f"Error processing prefix {prefix_cidr}: {str(e)}")

    return subnet_ips


def calculate_fragmentation(used_ips, total_ips, available_count):
    """
    Calculate fragmentation metrics for a subnet optimized for /28 prefix allocation.
    Returns a fragmentation score (0-100) where:
    - 0 = Low fragmentation (can allocate many /28 blocks efficiently)
    - 100 = High fragmentation (most available IPs are wasted in unusable fragments)

    The score measures what percentage of available IPs are in fragments too small
    to fit a /28 block (16 IPs). This directly reflects allocation efficiency.
    """
    PREFIX_SIZE = 16  # /28 block size for EKS prefix delegation

    if total_ips == 0 or available_count == 0:
        return 0, {'num_gaps': 0, 'avg_gap_size': 0, 'largest_gap': 0, 'gaps': [], 'usable_prefixes': 0}

    if len(used_ips) == 0:
        # No IPs used means no fragmentation
        usable_prefixes = available_count // PREFIX_SIZE
        return 0, {
            'num_gaps': 0,
            'avg_gap_size': 0,
            'largest_gap': available_count,
            'gaps': [],
            'usable_prefixes': usable_prefixes
        }

    # Sort used IPs by their integer representation
    sorted_used = sorted([int(ip_address(ip)) for ip in used_ips])

    logger.info(f"Fragmentation calc: total_ips={total_ips}, available={available_count}, used={len(used_ips)}")
    logger.info(f"Used IP range: {ip_address(sorted_used[0])} to {ip_address(sorted_used[-1])}")

    # Find all free blocks (gaps between used IPs + edge space)
    gaps = []
    for i in range(len(sorted_used) - 1):
        gap_size = sorted_used[i + 1] - sorted_used[i] - 1
        if gap_size > 0:
            gaps.append(gap_size)

    # Total IPs in gaps between used IPs
    total_gap_ips = sum(gaps)

    # The remaining available IPs are in contiguous blocks outside the used IP range
    edge_free_ips = available_count - total_gap_ips

    # All free blocks = gaps + edge block
    all_free_blocks = gaps + ([edge_free_ips] if edge_free_ips > 0 else [])

    # Calculate how many /28 prefixes can actually be allocated
    usable_prefixes = sum(block // PREFIX_SIZE for block in all_free_blocks)

    # Calculate how many /28 prefixes COULD be allocated if perfectly contiguous
    theoretical_prefixes = available_count // PREFIX_SIZE

    # Calculate wasted IPs (IPs in fragments too small for /28)
    wasted_ips = sum(block % PREFIX_SIZE if block < PREFIX_SIZE else 0
                     for block in all_free_blocks)
    # Add the remainder IPs from blocks that can fit prefixes
    wasted_ips += sum(block % PREFIX_SIZE for block in all_free_blocks if block >= PREFIX_SIZE)

    logger.info(f"Gaps: {len(gaps)} gaps totaling {total_gap_ips} IPs")
    logger.info(f"Free blocks: {sorted(all_free_blocks, reverse=True)[:5]}")
    logger.info(f"Can allocate {usable_prefixes} /28 prefixes (theoretical max: {theoretical_prefixes})")
    logger.info(f"Wasted IPs: {wasted_ips}/{available_count}")

    # Calculate metrics
    num_free_blocks = len(all_free_blocks)
    largest_free_block = max(all_free_blocks) if all_free_blocks else 0
    avg_block_size = sum(all_free_blocks) / num_free_blocks if num_free_blocks > 0 else 0

    # If all free space is in one block, fragmentation is minimal
    if num_free_blocks <= 1:
        # Still calculate score based on wasted remainder
        waste_percentage = (wasted_ips / available_count) * 100 if available_count > 0 else 0
        return round(waste_percentage, 2), {
            'num_gaps': 0,
            'avg_gap_size': 0,
            'largest_gap': largest_free_block,
            'gaps': [],
            'usable_prefixes': usable_prefixes
        }

    # Fragmentation score: percentage of IPs that can't be used due to fragmentation
    # This accounts for both small fragments AND remainder waste
    if theoretical_prefixes > 0:
        # How many prefixes are lost due to fragmentation?
        lost_prefixes = theoretical_prefixes - usable_prefixes
        fragmentation_score = (lost_prefixes / theoretical_prefixes) * 100
    else:
        # If we can't even fit one /28, fragmentation is maximum
        fragmentation_score = 100

    logger.info(f"Fragmentation score: {fragmentation_score:.1f}% (lost {theoretical_prefixes - usable_prefixes}/{theoretical_prefixes} possible /28 blocks)")

    return round(fragmentation_score, 2), {
        'num_gaps': len(gaps),
        'avg_gap_size': round(avg_block_size, 2),
        'largest_gap': largest_free_block,
        'gaps': sorted(all_free_blocks, reverse=True)[:10],
        'usable_prefixes': usable_prefixes
    }


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
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions(AllRegions=False)
        regions = [
            {
                'id': region['RegionName'],
                'name': region['RegionName'],
                'endpoint': region['Endpoint']
            }
            for region in response['Regions']
        ]
        # Sort by region name
        regions.sort(key=lambda x: x['name'])
        return jsonify(regions)
    except Exception as e:
        logger.error(f"Error fetching regions: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vpcs')
def get_vpcs():
    """Get all VPCs in the account for the specified region"""
    try:
        region = get_region_from_request()
        ec2_client = get_ec2_client(region)
        response = ec2_client.describe_vpcs()
        vpcs = []

        for vpc in response['Vpcs']:
            name = next((tag['Value'] for tag in vpc.get('Tags', [])
                        if tag['Key'] == 'Name'), vpc['VpcId'])
            vpcs.append({
                'id': vpc['VpcId'],
                'name': name,
                'cidr': vpc['CidrBlock'],
                'state': vpc['State']
            })

        return jsonify(vpcs)
    except Exception as e:
        logger.error(f"Error fetching VPCs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vpc/<vpc_id>/subnets')
def get_subnets(vpc_id):
    """Get all subnets for a VPC with usage statistics"""
    try:
        region = get_region_from_request()
        ec2_client = get_ec2_client(region)

        # Get subnets
        subnets_response = ec2_client.describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )

        # Get all ENIs for this VPC
        enis_response = ec2_client.describe_network_interfaces(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )

        # Extract all IPs from ENIs (including secondary IPs and prefix delegation)
        subnet_ip_details = get_all_eni_ips(enis_response['NetworkInterfaces'])

        subnets = []
        for subnet in subnets_response['Subnets']:
            if subnet.get('Ipv6Native', False):
                continue

            subnet_id = subnet['SubnetId']
            cidr_block = subnet['CidrBlock']

            name = next((tag['Value'] for tag in subnet.get('Tags', [])
                        if tag['Key'] == 'Name'), subnet_id)

            # Calculate IP usage
            network = ip_network(cidr_block)
            total_ips = network.num_addresses
            available_ips = subnet['AvailableIpAddressCount']

            # Get used IPs from ENIs (including secondary IPs and prefixes)
            ip_details = subnet_ip_details.get(subnet_id, [])
            used_ips = [ip_info['ip'] for ip_info in ip_details]
            reserved_ips = get_reserved_ips(cidr_block)

            # Get CIDR reservations
            cidr_reservation_ips = get_subnet_cidr_reservations(ec2_client, subnet_id)
            cidr_reservations_list = list(cidr_reservation_ips.keys())

            # Combine used IPs and CIDR reservations for fragmentation calculation
            # CIDR reservations should be treated as unavailable space
            all_unavailable_ips = used_ips + cidr_reservations_list

            # Calculate fragmentation
            logger.info(f"=== Calculating fragmentation for subnet: {name} ({subnet_id}) ===")
            frag_score, frag_details = calculate_fragmentation(
                all_unavailable_ips, total_ips, available_ips
            )

            # Count different IP types
            primary_count = sum(1 for ip in ip_details if ip['type'] == 'primary')
            secondary_count = sum(1 for ip in ip_details if ip['type'] == 'secondary')
            prefix_count = sum(1 for ip in ip_details if ip['type'] == 'prefix_delegation')

            # Extract unique CIDR reservation blocks for summary
            reservation_blocks = {}
            for ip_addr, res_info in cidr_reservation_ips.items():
                res_cidr = res_info['cidr']
                if res_cidr not in reservation_blocks:
                    reservation_blocks[res_cidr] = res_info

            subnets.append({
                'id': subnet_id,
                'name': name,
                'cidr': cidr_block,
                'availabilityZone': subnet['AvailabilityZone'],
                'totalIps': total_ips,
                'availableIps': available_ips,
                'usedIps': len(used_ips),
                'reservedIps': len(reserved_ips),
                'cidrReservationIps': len(cidr_reservations_list),
                'cidrReservations': list(reservation_blocks.values()),
                'primaryIps': primary_count,
                'secondaryIps': secondary_count,
                'prefixDelegationIps': prefix_count,
                'utilization': round((len(used_ips) / total_ips) * 100, 2) if total_ips > 0 else 0,
                'fragmentationScore': frag_score,
                'fragmentationDetails': frag_details
            })

        return jsonify(subnets)
    except Exception as e:
        logger.error(f"Error fetching subnets: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subnet/<subnet_id>/ips')
def get_subnet_ips(subnet_id):
    """Get detailed IP allocation map for a subnet"""
    try:
        region = get_region_from_request()
        ec2_client = get_ec2_client(region)

        # Get subnet details
        subnet_response = ec2_client.describe_subnets(SubnetIds=[subnet_id])
        subnet = subnet_response['Subnets'][0]
        cidr_block = subnet['CidrBlock']

        # Get ENIs in this subnet
        enis_response = ec2_client.describe_network_interfaces(
            Filters=[{'Name': 'subnet-id', 'Values': [subnet_id]}]
        )

        # Collect all IPs from ENIs (including secondary and prefix delegation)
        subnet_ip_details = get_all_eni_ips(enis_response['NetworkInterfaces'])
        ip_details_map = {ip_info['ip']: ip_info for ip_info in subnet_ip_details.get(subnet_id, [])}

        # Get reserved IPs (AWS system reserved)
        reserved_ips = get_reserved_ips(cidr_block)

        # Get CIDR reservations (explicit and prefix reservations)
        cidr_reservation_ips = get_subnet_cidr_reservations(ec2_client, subnet_id)

        # Build complete IP map
        network = ip_network(cidr_block)
        ip_map = []

        for ip in network:
            ip_str = str(ip)
            if ip_str in reserved_ips:
                status = 'reserved'
                details = {'reason': 'AWS Reserved', 'type': 'aws_reserved'}
            elif ip_str in ip_details_map:
                # IP is in use - show as used even if in a CIDR reservation
                status = 'used'
                details = ip_details_map[ip_str]
                # Add reservation info if this IP is also part of a CIDR reservation
                if ip_str in cidr_reservation_ips:
                    details['cidrReservation'] = cidr_reservation_ips[ip_str]
            elif ip_str in cidr_reservation_ips:
                # IP is reserved but not currently in use
                status = 'cidr_reservation'
                details = cidr_reservation_ips[ip_str]
            else:
                status = 'free'
                details = None

            ip_map.append({
                'ip': ip_str,
                'status': status,
                'details': details
            })

        # Calculate statistics
        used_count = sum(1 for ip in ip_map if ip['status'] == 'used')
        free_count = sum(1 for ip in ip_map if ip['status'] == 'free')
        reserved_count = sum(1 for ip in ip_map if ip['status'] == 'reserved')
        cidr_reservation_count = sum(1 for ip in ip_map if ip['status'] == 'cidr_reservation')

        return jsonify({
            'subnetId': subnet_id,
            'cidr': cidr_block,
            'totalIps': len(ip_map),
            'usedIps': used_count,
            'freeIps': free_count,
            'reservedIps': reserved_count,
            'cidrReservationIps': cidr_reservation_count,
            'ips': ip_map
        })
    except Exception as e:
        logger.error(f"Error fetching subnet IPs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'vpc-ip-fragmentation-viewer'})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
