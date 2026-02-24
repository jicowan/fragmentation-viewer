# Quick Start Guide

Get the VPC IP Fragmentation Viewer running in under 5 minutes!

## Prerequisites

Choose one of these setups:

### Option A: Docker (Easiest)
- Docker and Docker Compose installed
- AWS credentials configured (`~/.aws/credentials` or environment variables)

### Option B: Local Development
- Python 3.11+
- Node.js 18+
- AWS credentials configured

## Quick Start

### 1. Configure AWS Credentials

The application needs read-only access to EC2 APIs. Ensure you have AWS credentials configured:

```bash
# Option 1: AWS CLI credentials (recommended)
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Required IAM Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeNetworkInterfaces"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. Start the Application

#### Using the Quick Start Script (Recommended)

```bash
./start.sh
```

The script will guide you through starting either with Docker or local development.

#### Manual Start with Docker Compose

```bash
# Create .env file
cp .env.example .env

# Start all services
docker-compose up

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:5000
```

#### Manual Start - Local Development

```bash
# Terminal 1: Backend
./setup.sh
source venv/bin/activate
python app.py

# Terminal 2: Frontend
cd frontend
npm install
npm start
```

## Using the Application

1. **Select a VPC** from the dropdown at the top
2. **Browse subnets** in the left panel - they show:
   - IP utilization percentage
   - Fragmentation score
   - Primary, secondary, and prefix delegation IP counts
3. **Click a subnet** to see the detailed visualization
4. **Hover over IP blocks** in the visualization to see:
   - IP address
   - Status (used/free/reserved)
   - ENI details (for used IPs)
   - IP type (primary, secondary, prefix delegation)

## Understanding the Visualization

### Color Coding

- **Blue blocks** - Primary ENI IPs (EC2 instances, load balancers, etc.)
- **Cyan blocks** - Secondary IPs (EKS pods without dedicated ENIs)
- **Purple blocks** - Prefix delegation IPs (EKS prefix mode)
- **Gray blocks** - AWS reserved IPs (.0, .1, .2, .3, and last IP)
- **Light gray blocks** - Available/free IPs

### Fragmentation Score

- **0-20 (Green)** - Low fragmentation, most IPs are contiguous
- **21-50 (Orange)** - Moderate fragmentation, some scattered allocations
- **51-100 (Red)** - High fragmentation, many small gaps

High fragmentation can make it difficult to allocate large blocks of IPs, especially for:
- Prefix delegation (requires contiguous /28 blocks)
- Large EKS node groups
- Multiple secondary IPs per ENI

## Troubleshooting

### "Failed to fetch VPCs"

- **Check AWS credentials**: Run `aws sts get-caller-identity` to verify
- **Check IAM permissions**: Ensure you have the required EC2 describe permissions
- **Check region**: Verify you're looking at the correct AWS region

### Docker issues

```bash
# Rebuild containers
docker-compose down
docker-compose up --build

# View logs
docker-compose logs backend
docker-compose logs frontend
```

### Frontend doesn't load

```bash
# Clear React cache
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

## Next Steps

- **Deploy to ECS/EKS**: See [README.md](README.md) for deployment instructions
- **Customize**: Modify visualization colors, grid size, or add new metrics
- **Integrate**: Use the REST API endpoints in your own tools

## API Endpoints

- `GET /api/vpcs` - List all VPCs
- `GET /api/vpc/<vpc_id>/subnets` - Get subnets with statistics
- `GET /api/subnet/<subnet_id>/ips` - Get detailed IP allocation map
- `GET /api/health` - Health check

Example:
```bash
curl http://localhost:5000/api/vpcs
curl http://localhost:5000/api/vpc/vpc-12345/subnets
curl http://localhost:5000/api/subnet/subnet-67890/ips
```

## Tips

1. **Large subnets** (>/28) may take a moment to load the full IP map
2. **Refresh regularly** - IP allocations change as pods are created/deleted
3. **Monitor fragmentation** over time to identify allocation patterns
4. **High fragmentation** may indicate the need to recreate the subnet or consolidate workloads

## Support

For issues or questions:
- Check the [README.md](README.md) for detailed documentation
- Review the application logs for error messages
- Ensure AWS credentials and permissions are correct
