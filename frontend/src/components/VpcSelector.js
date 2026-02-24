import React from 'react';
import './VpcSelector.css';

function VpcSelector({ vpcs, selectedVpc, onSelect, loading }) {
  return (
    <div className="vpc-selector">
      <label htmlFor="vpc-select">Select VPC:</label>
      <select
        id="vpc-select"
        value={selectedVpc?.id || ''}
        onChange={(e) => {
          const vpc = vpcs.find(v => v.id === e.target.value);
          onSelect(vpc || null);
        }}
        disabled={loading}
      >
        <option value="">-- Select a VPC --</option>
        {vpcs.map(vpc => (
          <option key={vpc.id} value={vpc.id}>
            {vpc.name} ({vpc.cidr}) - {vpc.id}
          </option>
        ))}
      </select>
    </div>
  );
}

export default VpcSelector;
