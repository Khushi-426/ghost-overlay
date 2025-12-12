import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LineChart, Line, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { ArrowLeft, Activity, ShieldCheck, AlertTriangle, Zap, Calendar } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';

const RiskPrediction = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      if (user?.email) {
        try {
          const res = await axios.post('http://127.0.0.1:5000/api/user/ai_prediction', { email: user.email });
          setData(res.data);
        } catch (err) { console.error(err); } finally { setLoading(false); }
      }
    };
    fetchData();
  }, [user]);

  if (loading) return <div style={{ height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#F9F7F3' }}>Loading AI Models...</div>;
  if (!data) return <div style={{padding:'50px', textAlign:'center'}}>No workout data available to analyze.</div>;

  const radarData = [
    { subject: 'Right Arm', A: data.asymmetry.right, fullMark: 150 },
    { subject: 'Left Arm', A: data.asymmetry.left, fullMark: 150 },
    { subject: 'Stability', A: data.stability_score, fullMark: 100 },
    { subject: 'ROM', A: data.rom_chart.length > 0 ? data.rom_chart[data.rom_chart.length-1].rom : 0, fullMark: 180 },
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#F9F7F3', padding: '40px 5%' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '40px' }}>
          <div>
            <h1 style={{ fontSize: '2.5rem', fontWeight: '800', color: '#1A3C34' }}>AI Recovery <span style={{color:'#69B341'}}>Prediction</span></h1>
            <p style={{ color: '#666' }}>Biomechanics analysis & injury risk assessment.</p>
          </div>
          <button onClick={() => navigate('/profile/overview')} style={{ background: '#fff', border: '1px solid #ddd', padding: '10px 20px', borderRadius: '30px', cursor:'pointer' }}>Back to Profile</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '25px' }}>
            {/* ROM CHART */}
            <div style={{ background: '#fff', padding: '30px', borderRadius: '24px', boxShadow: '0 5px 15px rgba(0,0,0,0.03)' }}>
                <h3 style={{ color: '#1A3C34', display: 'flex', gap: '10px' }}><Activity color="#69B341"/> Joint Range of Motion</h3>
                <div style={{ height: '250px' }}>
                    <ResponsiveContainer><LineChart data={data.rom_chart}><CartesianGrid stroke="#eee"/><XAxis dataKey="date"/><YAxis domain={[0, 180]}/><Tooltip/><Line type="monotone" dataKey="rom" stroke="#2C5D31" strokeWidth={3}/></LineChart></ResponsiveContainer>
                </div>
            </div>

            {/* RADAR CHART */}
            <div style={{ background: '#fff', padding: '30px', borderRadius: '24px', boxShadow: '0 5px 15px rgba(0,0,0,0.03)' }}>
                <h3 style={{ color: '#1A3C34', display: 'flex', gap: '10px' }}><Zap color="#FF9800"/> Symmetry Score</h3>
                <div style={{ height: '250px' }}>
                    <ResponsiveContainer><RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}><PolarGrid/><PolarAngleAxis dataKey="subject"/><PolarRadiusAxis angle={30} domain={[0, 150]}/><Radar dataKey="A" stroke="#69B341" fill="#69B341" fillOpacity={0.5}/><Tooltip/></RadarChart></ResponsiveContainer>
                </div>
            </div>

            {/* BODY MAP */}
            <div style={{ background: '#fff', padding: '30px', borderRadius: '24px', position: 'relative', boxShadow: '0 5px 15px rgba(0,0,0,0.03)' }}>
                <h3 style={{ color: '#1A3C34', display: 'flex', gap: '10px' }}><AlertTriangle color="#D32F2F"/> Error Hotspots</h3>
                <div style={{ height: '250px', display: 'flex', justifyContent: 'center', position: 'relative' }}>
                    <svg height="220" viewBox="0 0 100 200" fill="#e0e0e0">
                        <circle cx="50" cy="20" r="15" /><rect x="35" y="35" width="30" height="70" rx="5" /><rect x="15" y="40" width="15" height="60" rx="5" /><rect x="70" y="40" width="15" height="60" rx="5" /><rect x="30" y="110" width="12" height="80" rx="5" /><rect x="58" y="110" width="12" height="80" rx="5" />
                    </svg>
                    <div title="Shoulder" style={{ position: 'absolute', top: '50px', right: '110px', width: '20px', height: '20px', borderRadius: '50%', background: `rgba(211, 47, 47, ${data.hotspots.shoulder/50})`, border: '2px solid white' }} />
                    <div title="Elbow" style={{ position: 'absolute', top: '90px', right: '100px', width: '15px', height: '15px', borderRadius: '50%', background: `rgba(255, 152, 0, ${data.hotspots.elbow/30})`, border: '2px solid white' }} />
                </div>
            </div>

            {/* RECOMMENDATIONS */}
            <div style={{ background: '#fff', padding: '30px', borderRadius: '24px', gridColumn: '1 / -1', boxShadow: '0 5px 15px rgba(0,0,0,0.03)' }}>
                <h3 style={{ color: '#1A3C34', display: 'flex', gap: '10px' }}><ShieldCheck color="#69B341"/> AI Recommendations</h3>
                {data.recommendations.map((rec, i) => (
                    <div key={i} style={{ background: '#F1F8E9', padding: '15px', borderRadius: '10px', marginBottom: '10px', color: '#33691E' }}>{rec}</div>
                ))}
            </div>
        </div>
      </div>
    </div>
  );
};
export default RiskPrediction;