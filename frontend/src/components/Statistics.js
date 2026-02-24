import React from 'react';
import './Statistics.css';

function Statistics({ subnet, ipData }) {
  const getFragmentationLevel = (score) => {
    if (score < 20) return { level: 'Low', color: '#10b981' };
    if (score < 50) return { level: 'Moderate', color: '#f59e0b' };
    return { level: 'High', color: '#ef4444' };
  };

  const fragInfo = getFragmentationLevel(subnet.fragmentationScore);

  return (
    <div className="statistics">
      <h3>Subnet Statistics: {subnet.name}</h3>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">IP Allocation</div>
          <div className="stat-card-body">
            <div className="stat-row">
              <span>Total IPs:</span>
              <strong>{subnet.totalIps}</strong>
            </div>
            <div className="stat-row">
              <span>Used IPs:</span>
              <strong>{subnet.usedIps}</strong>
            </div>
            <div className="stat-row">
              <span>Available IPs:</span>
              <strong>{subnet.availableIps}</strong>
            </div>
            <div className="stat-row">
              <span>Reserved (AWS):</span>
              <strong>{subnet.reservedIps}</strong>
            </div>
            <div className="stat-row highlight">
              <span>Utilization:</span>
              <strong>{subnet.utilization.toFixed(2)}%</strong>
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">IP Types (EKS)</div>
          <div className="stat-card-body">
            <div className="stat-row">
              <span>Primary ENI IPs:</span>
              <strong>{subnet.primaryIps}</strong>
            </div>
            <div className="stat-row">
              <span>Secondary IPs:</span>
              <strong>{subnet.secondaryIps}</strong>
            </div>
            <div className="stat-row">
              <span>Prefix Delegation:</span>
              <strong>{subnet.prefixDelegationIps}</strong>
            </div>
          </div>
        </div>

        <div className="stat-card fragmentation-card" style={{ borderColor: fragInfo.color }}>
          <div className="stat-card-header" style={{ backgroundColor: fragInfo.color }}>
            Fragmentation Analysis
          </div>
          <div className="stat-card-body">
            <div className="frag-score" style={{ color: fragInfo.color }}>
              <span className="frag-score-value">{subnet.fragmentationScore.toFixed(1)}</span>
              <span className="frag-score-label">{fragInfo.level}</span>
            </div>
            {subnet.fragmentationDetails && (
              <>
                <div className="stat-row">
                  <span>Number of Gaps:</span>
                  <strong>{subnet.fragmentationDetails.num_gaps}</strong>
                </div>
                <div className="stat-row">
                  <span>Largest Free Block:</span>
                  <strong>{subnet.fragmentationDetails.largest_gap} IPs</strong>
                </div>
                <div className="stat-row">
                  <span>Average Gap Size:</span>
                  <strong>{subnet.fragmentationDetails.avg_gap_size.toFixed(1)} IPs</strong>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="subnet-info">
        <div className="info-row">
          <span>Subnet ID:</span>
          <code>{subnet.id}</code>
        </div>
        <div className="info-row">
          <span>CIDR Block:</span>
          <code>{subnet.cidr}</code>
        </div>
        <div className="info-row">
          <span>Availability Zone:</span>
          <code>{subnet.availabilityZone}</code>
        </div>
      </div>
    </div>
  );
}

export default Statistics;
