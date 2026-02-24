import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import RegionSelector from './components/RegionSelector';
import VpcSelector from './components/VpcSelector';
import SubnetList from './components/SubnetList';
import IpVisualization from './components/IpVisualization';
import Statistics from './components/Statistics';

const API_URL = process.env.REACT_APP_API_URL || '';

function App() {
  const [regions, setRegions] = useState([]);
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [vpcs, setVpcs] = useState([]);
  const [selectedVpc, setSelectedVpc] = useState(null);
  const [subnets, setSubnets] = useState([]);
  const [selectedSubnet, setSelectedSubnet] = useState(null);
  const [ipData, setIpData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch regions on mount
  useEffect(() => {
    fetchRegions();
  }, []);

  // Fetch VPCs when region is selected
  useEffect(() => {
    if (selectedRegion) {
      fetchVpcs();
    } else {
      setVpcs([]);
      setSelectedVpc(null);
      setSubnets([]);
      setSelectedSubnet(null);
      setIpData(null);
    }
  }, [selectedRegion]);

  // Fetch subnets when VPC is selected
  useEffect(() => {
    if (selectedVpc) {
      fetchSubnets(selectedVpc.id);
    } else {
      setSubnets([]);
      setSelectedSubnet(null);
      setIpData(null);
    }
  }, [selectedVpc]);

  // Fetch IP data when subnet is selected
  useEffect(() => {
    if (selectedSubnet) {
      fetchIpData(selectedSubnet.id);
    } else {
      setIpData(null);
    }
  }, [selectedSubnet]);

  const fetchRegions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_URL}/api/regions`);
      setRegions(response.data);
      // Auto-select us-east-1 or first region
      const defaultRegion = response.data.find(r => r.id === 'us-east-1') || response.data[0];
      if (defaultRegion) {
        setSelectedRegion(defaultRegion);
      }
    } catch (err) {
      setError('Failed to fetch regions: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchVpcs = async () => {
    if (!selectedRegion) return;
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_URL}/api/vpcs`, {
        params: { region: selectedRegion.id }
      });
      setVpcs(response.data);
    } catch (err) {
      setError('Failed to fetch VPCs: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchSubnets = async (vpcId) => {
    if (!selectedRegion) return;
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_URL}/api/vpc/${vpcId}/subnets`, {
        params: { region: selectedRegion.id }
      });
      setSubnets(response.data);
    } catch (err) {
      setError('Failed to fetch subnets: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchIpData = async (subnetId) => {
    if (!selectedRegion) return;
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_URL}/api/subnet/${subnetId}/ips`, {
        params: { region: selectedRegion.id }
      });
      setIpData(response.data);
    } catch (err) {
      setError('Failed to fetch IP data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    if (selectedVpc) {
      fetchSubnets(selectedVpc.id);
    } else if (selectedRegion) {
      fetchVpcs();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>☁️ VPC IP Fragmentation Viewer</h1>
        <p>Visualize IP address allocation and fragmentation in AWS VPCs</p>
      </header>

      <div className="App-content">
        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
            <button onClick={handleRefresh}>Retry</button>
          </div>
        )}

        <div className="controls-section">
          <RegionSelector
            regions={regions}
            selectedRegion={selectedRegion}
            onSelect={setSelectedRegion}
            loading={loading}
          />
          <VpcSelector
            vpcs={vpcs}
            selectedVpc={selectedVpc}
            onSelect={setSelectedVpc}
            loading={loading}
          />
          {selectedVpc && (
            <button className="refresh-button" onClick={handleRefresh}>
              Refresh
            </button>
          )}
        </div>

        {selectedVpc && (
          <div className="main-content">
            <div className="left-panel">
              <SubnetList
                subnets={subnets}
                selectedSubnet={selectedSubnet}
                onSelect={setSelectedSubnet}
                loading={loading}
              />
            </div>

            <div className="right-panel">
              {selectedSubnet && ipData ? (
                <>
                  <Statistics subnet={selectedSubnet} ipData={ipData} />
                  <IpVisualization ipData={ipData} />
                </>
              ) : (
                <div className="placeholder">
                  <h3>Select a subnet to view IP allocation</h3>
                  <p>Click on a subnet from the list to see its IP fragmentation visualization</p>
                </div>
              )}
            </div>
          </div>
        )}

        {!selectedVpc && !loading && selectedRegion && (
          <div className="welcome-message">
            <h2>Welcome to VPC IP Fragmentation Viewer</h2>
            <p>Select a VPC from the dropdown above to get started</p>
            <div className="legend">
              <h3>Color Legend:</h3>
              <div className="legend-items">
                <div className="legend-item">
                  <span className="color-box used"></span>
                  <span>Used IP (Primary ENI)</span>
                </div>
                <div className="legend-item">
                  <span className="color-box secondary"></span>
                  <span>Used IP (Secondary/EKS Pod)</span>
                </div>
                <div className="legend-item">
                  <span className="color-box prefix"></span>
                  <span>Used IP (Prefix Delegation)</span>
                </div>
                <div className="legend-item">
                  <span className="color-box reserved"></span>
                  <span>Reserved (AWS)</span>
                </div>
                <div className="legend-item">
                  <span className="color-box free"></span>
                  <span>Free/Available</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
