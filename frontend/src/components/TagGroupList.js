import React from 'react';
import './TagGroupList.css';

function TagGroupList({ tagGroups, vpcUsedIps, onGroupClick, loading }) {
  if (loading) {
    return <div className="tag-group-list-loading">Loading tag groups...</div>;
  }

  if (!tagGroups || tagGroups.length === 0) {
    return <div className="tag-group-list-empty">No tag groups found. Select a tag key above.</div>;
  }

  const getFragmentationColor = (score) => {
    if (score < 20) return '#10b981';
    if (score < 50) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="tag-group-list">
      <h3>Tag Groups ({tagGroups.length})</h3>
      <div className="tag-group-items">
        {tagGroups.map(group => (
          <div
            key={group.tagValue}
            className="tag-group-item"
            onClick={() => onGroupClick(group)}
          >
            <div className="tag-group-header">
              <h4>{group.tagValue}</h4>
              <span className="tag-group-subnet-count">
                {group.subnetCount} subnet{group.subnetCount !== 1 ? 's' : ''}
              </span>
            </div>

            <div className="tag-group-stats">
              <div className="stat">
                <span className="stat-label">IPs Used:</span>
                <span className="stat-value">{group.totalIpsUsed}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Share of VPC:</span>
                <span className="stat-value">{group.utilizationPercent.toFixed(1)}%</span>
              </div>
            </div>

            <div className="tag-group-ip-types">
              {group.primaryIps > 0 && (
                <span className="ip-type-badge primary">Primary: {group.primaryIps}</span>
              )}
              {group.secondaryIps > 0 && (
                <span className="ip-type-badge secondary">Secondary: {group.secondaryIps}</span>
              )}
              {group.prefixDelegationIps > 0 && (
                <span className="ip-type-badge prefix">Prefix: {group.prefixDelegationIps}</span>
              )}
            </div>

            <div className="fragmentation-score">
              <span className="frag-label">Fragmentation:</span>
              <div className="frag-bar-container">
                <div
                  className="frag-bar"
                  style={{
                    width: `${group.fragmentationScore}%`,
                    backgroundColor: getFragmentationColor(group.fragmentationScore)
                  }}
                />
              </div>
              <span className="frag-value">{group.fragmentationScore.toFixed(1)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TagGroupList;
