import React, { useState } from 'react';
import './IpVisualization.css';

function IpVisualization({ ipData }) {
  const [hoveredIp, setHoveredIp] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const getIpColor = (ip) => {
    switch (ip.status) {
      case 'used':
        // Differentiate by type if details available
        if (ip.details?.type === 'primary') {
          return '#3b82f6'; // Blue - primary ENI
        } else if (ip.details?.type === 'secondary') {
          return '#06b6d4'; // Cyan - secondary (EKS pods)
        } else if (ip.details?.type === 'prefix_delegation') {
          return '#8b5cf6'; // Purple - prefix delegation
        }
        return '#3b82f6'; // Default blue
      case 'reserved':
        return '#9ca3af'; // Gray - AWS reserved
      case 'cidr_reservation':
        // Differentiate by reservation type
        if (ip.details?.type === 'explicit') {
          return '#f59e0b'; // Amber - explicit reservation
        } else if (ip.details?.type === 'prefix') {
          return '#f97316'; // Orange - prefix reservation
        }
        return '#f59e0b'; // Default amber
      case 'free':
        return '#f3f4f6'; // Light gray - available
      default:
        return '#f3f4f6';
    }
  };

  const getIpLabel = (ip) => {
    const lastOctet = ip.ip.split('.').pop();
    return lastOctet;
  };

  const handleMouseEnter = (ip, event) => {
    const rect = event.target.getBoundingClientRect();
    setTooltipPos({
      x: rect.left + rect.width / 2,
      y: rect.top - 10
    });
    setHoveredIp(ip);
  };

  const handleMouseLeave = () => {
    setHoveredIp(null);
  };

  // Calculate grid dimensions
  // For better visualization, we'll use 32 columns (similar to disk defrag tools)
  const COLS = 32;
  const totalIps = ipData.ips.length;

  return (
    <div className="ip-visualization">
      <div className="visualization-header">
        <h3>IP Address Map</h3>
        <div className="legend-compact">
          <div className="legend-item-compact">
            <span className="color-dot" style={{ backgroundColor: '#3b82f6' }}></span>
            <span>Primary</span>
          </div>
          <div className="legend-item-compact">
            <span className="color-dot" style={{ backgroundColor: '#06b6d4' }}></span>
            <span>Secondary</span>
          </div>
          <div className="legend-item-compact">
            <span className="color-dot" style={{ backgroundColor: '#8b5cf6' }}></span>
            <span>Prefix</span>
          </div>
          <div className="legend-item-compact">
            <span className="color-dot" style={{ backgroundColor: '#f59e0b' }}></span>
            <span>CIDR Resv</span>
          </div>
          <div className="legend-item-compact">
            <span className="color-dot" style={{ backgroundColor: '#9ca3af' }}></span>
            <span>AWS Resv</span>
          </div>
          <div className="legend-item-compact">
            <span className="color-dot" style={{ backgroundColor: '#f3f4f6' }}></span>
            <span>Free</span>
          </div>
        </div>
      </div>

      <div className="ip-grid-container">
        <div className="ip-grid" style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)` }}>
          {ipData.ips.map((ip, index) => {
            // Check if this IP is both used and in a CIDR reservation
            const hasReservationOverlap = ip.status === 'used' && ip.details?.cidrReservation;

            return (
              <div
                key={index}
                className={`ip-block ${ip.status} ${hasReservationOverlap ? 'has-reservation' : ''}`}
                style={{ backgroundColor: getIpColor(ip) }}
                onMouseEnter={(e) => handleMouseEnter(ip, e)}
                onMouseLeave={handleMouseLeave}
                title={ip.ip}
              >
              {/* Show label for every 4th IP or important IPs */}
              {(index % 4 === 0 || ip.status === 'used') && (
                <span className="ip-label">{getIpLabel(ip)}</span>
              )}
            </div>
            );
          })}
        </div>
      </div>

      {hoveredIp && (
        <div
          className="ip-tooltip"
          style={{
            left: `${tooltipPos.x}px`,
            top: `${tooltipPos.y}px`,
          }}
        >
          <div className="tooltip-header">
            <strong>{hoveredIp.ip}</strong>
          </div>
          <div className="tooltip-body">
            <div className="tooltip-row">
              <span>Status:</span>
              <span className={`status-badge ${hoveredIp.status}`}>
                {hoveredIp.status.toUpperCase()}
              </span>
            </div>
            {hoveredIp.status === 'used' && hoveredIp.details && (
              <>
                {hoveredIp.details.type && (
                  <div className="tooltip-row">
                    <span>Type:</span>
                    <span>{hoveredIp.details.type.replace('_', ' ')}</span>
                  </div>
                )}
                {hoveredIp.details.interfaceId && (
                  <div className="tooltip-row">
                    <span>ENI:</span>
                    <span className="mono">{hoveredIp.details.interfaceId}</span>
                  </div>
                )}
                {hoveredIp.details.description && (
                  <div className="tooltip-row">
                    <span>Description:</span>
                    <span>{hoveredIp.details.description}</span>
                  </div>
                )}
                {hoveredIp.details.status && (
                  <div className="tooltip-row">
                    <span>ENI Status:</span>
                    <span>{hoveredIp.details.status}</span>
                  </div>
                )}
                {hoveredIp.details.cidrReservation && (
                  <>
                    <div className="tooltip-divider"></div>
                    <div className="tooltip-row">
                      <span>CIDR Reservation:</span>
                      <span className="mono">{hoveredIp.details.cidrReservation.cidr}</span>
                    </div>
                    <div className="tooltip-row">
                      <span>Reservation Type:</span>
                      <span>{hoveredIp.details.cidrReservation.type}</span>
                    </div>
                    {hoveredIp.details.cidrReservation.description && (
                      <div className="tooltip-row">
                        <span>Reservation Desc:</span>
                        <span>{hoveredIp.details.cidrReservation.description}</span>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
            {hoveredIp.status === 'reserved' && hoveredIp.details && (
              <div className="tooltip-row">
                <span>Reason:</span>
                <span>{hoveredIp.details.reason}</span>
              </div>
            )}
            {hoveredIp.status === 'cidr_reservation' && hoveredIp.details && (
              <>
                <div className="tooltip-row">
                  <span>Reservation Type:</span>
                  <span>{hoveredIp.details.type}</span>
                </div>
                <div className="tooltip-row">
                  <span>CIDR Block:</span>
                  <span className="mono">{hoveredIp.details.cidr}</span>
                </div>
                {hoveredIp.details.description && (
                  <div className="tooltip-row">
                    <span>Description:</span>
                    <span>{hoveredIp.details.description}</span>
                  </div>
                )}
                {hoveredIp.details.reservationId && (
                  <div className="tooltip-row">
                    <span>ID:</span>
                    <span className="mono">{hoveredIp.details.reservationId}</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      <div className="visualization-summary">
        <p>
          Displaying <strong>{totalIps}</strong> IP addresses in a{' '}
          <strong>{Math.ceil(totalIps / COLS)} × {COLS}</strong> grid
        </p>
        <p className="help-text">
          Hover over any block to see IP details. Each block represents one IP address.
        </p>
      </div>
    </div>
  );
}

export default IpVisualization;
