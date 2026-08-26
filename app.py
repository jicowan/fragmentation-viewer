#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#

import logging
import os
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from dotenv import load_dotenv

from vpc_data import (
    DEFAULT_REGION,
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


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'vpc-ip-fragmentation-viewer'})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
