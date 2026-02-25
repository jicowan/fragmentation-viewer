import React from 'react';
import './SubnetList.css';

function SubnetList({ subnets, selectedSubnet, onSelect, loading }) {
  if (loading) {
    return <div className="subnet-list-loading">Loading subnets...</div>;
  }

  if (subnets.length === 0) {
    return <div className="subnet-list-empty">No subnets found</div>;
  }

  const getFragmentationColor = (score) => {
    if (score < 20) return '#10b981'; // Green - low fragmentation
    if (score < 50) return '#f59e0b'; // Orange - moderate
    return '#ef4444'; // Red - high fragmentation
  };

  return (
    <div className="subnet-list">
      <h3>Subnets ({subnets.length})</h3>
      <div className="subnet-items">
        {subnets.map(subnet => (
          <div
            key={subnet.id}
            className={`subnet-item ${selectedSubnet?.id === subnet.id ? 'selected' : ''}`}
            onClick={() => onSelect(subnet)}
          >
            <div className="subnet-header">
              <h4>{subnet.name}</h4>
              <span className="subnet-az">{subnet.availabilityZone}</span>
            </div>
            <div className="subnet-cidr">{subnet.cidr}</div>
            <div className="subnet-stats">
              <div className="stat">
                <span className="stat-label">Utilization:</span>
                <span className="stat-value">{subnet.utilization.toFixed(1)}%</span>
              </div>
              <div className="stat">
                <span className="stat-label">Used:</span>
                <span className="stat-value">{subnet.usedIps}/{subnet.totalIps}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Available:</span>
                <span className="stat-value">{subnet.availableIps}</span>
              </div>
            </div>
            <div className="subnet-ip-types">
              {subnet.primaryIps > 0 && (
                <span className="ip-type-badge primary">Primary: {subnet.primaryIps}</span>
              )}
              {subnet.secondaryIps > 0 && (
                <span className="ip-type-badge secondary">Secondary: {subnet.secondaryIps}</span>
              )}
              {subnet.prefixDelegationIps > 0 && (
                <span className="ip-type-badge prefix">Prefix: {subnet.prefixDelegationIps}</span>
              )}
              {subnet.cidrReservationIps > 0 && (
                <span className="ip-type-badge cidr-reservation">CIDR Resv: {subnet.cidrReservationIps}</span>
              )}
            </div>
            {subnet.cidrReservations && subnet.cidrReservations.length > 0 && (
              <div className="subnet-reservations">
                <span className="reservations-label">Reservations:</span>
                {subnet.cidrReservations.map((resv, idx) => (
                  <div key={idx} className="reservation-item">
                    <span className="reservation-cidr">{resv.cidr}</span>
                    <span className="reservation-type">({resv.type})</span>
                  </div>
                ))}
              </div>
            )}
            <div className="fragmentation-score">
              <span className="frag-label">Fragmentation:</span>
              <div className="frag-bar-container">
                <div
                  className="frag-bar"
                  style={{
                    width: `${subnet.fragmentationScore}%`,
                    backgroundColor: getFragmentationColor(subnet.fragmentationScore)
                  }}
                />
              </div>
              <span className="frag-value">{subnet.fragmentationScore.toFixed(1)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SubnetList;
