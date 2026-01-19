import React, { useState, useMemo, useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import { Eye, EyeOff, TrendingUp } from "lucide-react";

// Generate daily data from July 1, 2021 to today
const generateDailyData = () => {
  const startDate = new Date('2021-07-01');
  const today = new Date();
  const data = [];
  
  let currentDate = new Date(startDate);
  let index = 0;
  
  while (currentDate <= today) {
    const dateStr = currentDate.toISOString().split('T')[0];
    
    // Generate realistic data
    const kolmoDeviation = Math.sin(index * 0.02) * 5 + (Math.random() - 0.5) * 3;
    
    const me4uRate = 1.15 + index * 0.001 + Math.random() * 0.05;
    const iou2Rate = 1.08 + index * 0.0008 + Math.random() * 0.04;
    const uomeRate = 1.12 + index * 0.0009 + Math.random() * 0.045;
    
    const relPathME4U = 100 + index * 0.05 + Math.random() * 2;
    const relPathIOU2 = 100 + index * 0.04 + Math.random() * 1.8;
    const relPathUOME = 100 + index * 0.045 + Math.random() * 1.9;
    
    // Determine winner based on relPath
    const relPaths = { ME4U: relPathME4U, IOU2: relPathIOU2, UOME: relPathUOME };
    const winner = Object.entries(relPaths).reduce((a, b) => a[1] > b[1] ? a : b)[0];
    
    data.push({
      date: dateStr,
      dateObj: new Date(currentDate),
      kolmoDeviation,
      me4uRate,
      iou2Rate,
      uomeRate,
      relPathME4U,
      relPathIOU2,
      relPathUOME,
      winner,
      traceId: `TRACE-${index.toString().padStart(6, '0')}`,
    });
    
    currentDate.setDate(currentDate.getDate() + 1);
    index++;
  }
  
  return data;
};

export default function App() {
  const allData = useMemo(() => generateDailyData(), []);
  const plotRef = useRef<HTMLDivElement>(null);
  
  // Date range state (indices)
  const [startIndex, setStartIndex] = useState(Math.max(0, allData.length - 365)); // Last year by default
  const [endIndex, setEndIndex] = useState(allData.length - 1);
  
  // Active layers state
  const [activeLines, setActiveLines] = useState({
    kolmoDeviation: true,
    relPathME4U: true,
    relPathIOU2: true,
    relPathUOME: true,
    me4uRate: true,
    iou2Rate: true,
    uomeRate: true,
  });
  
  // Get filtered data based on range
  const filteredData = useMemo(() => {
    return allData.slice(startIndex, endIndex + 1);
  }, [allData, startIndex, endIndex]);
  
  // Calculate volatility data for each day in filtered range
  const volatilityData = useMemo(() => {
    return filteredData.map((currentDay, index) => {
      // Find previous day's data (either from filtered data or from allData before the filtered range)
      const globalIndex = startIndex + index;
      const prevDay = globalIndex > 0 ? allData[globalIndex - 1] : null;
      
      let me4uVol = 0;
      let iou2Vol = 0;
      let uomeVol = 0;
      
      if (prevDay) {
        // Calculate volatility: (rate_today - rate_yesterday) / rate_yesterday × 100
        me4uVol = ((currentDay.me4uRate - prevDay.me4uRate) / prevDay.me4uRate) * 100;
        iou2Vol = ((currentDay.iou2Rate - prevDay.iou2Rate) / prevDay.iou2Rate) * 100;
        uomeVol = ((currentDay.uomeRate - prevDay.uomeRate) / prevDay.uomeRate) * 100;
      }
      
      return {
        ...currentDay,
        me4uVolatility: me4uVol,
        iou2Volatility: iou2Vol,
        uomeVolatility: uomeVol,
      };
    });
  }, [filteredData, allData, startIndex]);
  
  // Get current (last) values
  const currentData = volatilityData[volatilityData.length - 1] || volatilityData[0];
  
  // Determine winner
  const relPaths = {
    IOU2: currentData.relPathIOU2,
    ME4U: currentData.relPathME4U,
    UOME: currentData.relPathUOME,
  };
  const winner = Object.entries(relPaths).reduce((a, b) => a[1] > b[1] ? a : b)[0];
  
  // Calculate Y-axis domains based on extreme values in filtered data
  const yAxisDomains = useMemo(() => {
    // KOLMO Deviation domain
    const kolmoValues = filteredData.map(d => d.kolmoDeviation);
    const kolmoMin = Math.min(...kolmoValues);
    const kolmoMax = Math.max(...kolmoValues);
    const kolmoPadding = (kolmoMax - kolmoMin) * 0.1;
    
    // Volatility domain (for Layer A - now showing volatility percentages)
    const volatilityValues = volatilityData.flatMap(d => [
      d.me4uVolatility,
      d.iou2Volatility,
      d.uomeVolatility,
    ]);
    const volatilityMin = Math.min(...volatilityValues);
    const volatilityMax = Math.max(...volatilityValues);
    const volatilityPadding = Math.max((volatilityMax - volatilityMin) * 0.1, 0.5);
    
    // General Rates domain (for stacked expanded - normalized to 100%)
    const generalMin = 0;
    const generalMax = 100;
    
    return {
      deviation: [
        kolmoMin - kolmoPadding,
        kolmoMax + kolmoPadding,
      ],
      volatility: [
        volatilityMin - volatilityPadding,
        volatilityMax + volatilityPadding,
      ],
      general: [generalMin, generalMax],
    };
  }, [filteredData, volatilityData]);
  
  // Render Plotly chart
  useEffect(() => {
    if (!plotRef.current) return;
    
    const dates = filteredData.map(d => d.dateObj);
    
    // Calculate normalized stacked area percentages for GENERAL RATES
    const totalRates = filteredData.map(d => d.me4uRate + d.iou2Rate + d.uomeRate);
    const me4uPercent = filteredData.map((d, i) => (d.me4uRate / totalRates[i]) * 100);
    const iou2Percent = filteredData.map((d, i) => (d.iou2Rate / totalRates[i]) * 100);
    const uomePercent = filteredData.map((d, i) => (d.uomeRate / totalRates[i]) * 100);
    
    const traces: any[] = [];
    
    // Layer B: GENERAL RATES - Stacked Expanded Area Charts (different opacity values)
    if (activeLines.me4uRate) {
      traces.push({
        x: dates,
        y: me4uPercent,
        name: 'ME4U Rate',
        type: 'scatter',
        mode: 'none',
        fill: 'tonexty',
        fillcolor: 'rgba(217, 95, 89, 0.15)',
        line: { color: 'rgba(217, 95, 89, 0.15)', width: 0 },
        stackgroup: 'general',
        groupnorm: 'percent',
        yaxis: 'y3',
        hovertemplate: '<b>ME4U Rate</b><br>%{y:.2f}%<extra></extra>',
      });
    }
    
    if (activeLines.iou2Rate) {
      traces.push({
        x: dates,
        y: iou2Percent,
        name: 'IOU2 Rate',
        type: 'scatter',
        mode: 'none',
        fill: 'tonexty',
        fillcolor: 'rgba(0, 135, 108, 0.18)',
        line: { color: 'rgba(0, 135, 108, 0.18)', width: 0 },
        stackgroup: 'general',
        groupnorm: 'percent',
        yaxis: 'y3',
        hovertemplate: '<b>IOU2 Rate</b><br>%{y:.2f}%<extra></extra>',
      });
    }
    
    if (activeLines.uomeRate) {
      traces.push({
        x: dates,
        y: uomePercent,
        name: 'UOME Rate',
        type: 'scatter',
        mode: 'none',
        fill: 'tonexty',
        fillcolor: 'rgba(168, 159, 60, 0.20)',
        line: { color: 'rgba(168, 159, 60, 0.20)', width: 0 },
        stackgroup: 'general',
        groupnorm: 'percent',
        yaxis: 'y3',
        hovertemplate: '<b>UOME Rate</b><br>%{y:.2f}%<extra></extra>',
      });
    }
    
    // Layer A: RELATIVE RATES - Line Charts with Markers showing Volatility
    if (activeLines.relPathME4U) {
      traces.push({
        x: dates,
        y: volatilityData.map(d => d.me4uVolatility),
        name: 'ME4U Volatility',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#C08060', width: 2.5 },
        marker: { 
          color: '#C08060', 
          size: 6,
          line: { color: 'white', width: 1 }
        },
        yaxis: 'y2',
        hovertemplate: '<b>ME4U Volatility</b><br>%{y:.3f}%<extra></extra>',
      });
    }
    
    if (activeLines.relPathIOU2) {
      traces.push({
        x: dates,
        y: volatilityData.map(d => d.iou2Volatility),
        name: 'IOU2 Volatility',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#5B4E7C', width: 2.5 },
        marker: { 
          color: '#5B4E7C', 
          size: 6,
          line: { color: 'white', width: 1 }
        },
        yaxis: 'y2',
        hovertemplate: '<b>IOU2 Volatility</b><br>%{y:.3f}%<extra></extra>',
      });
    }
    
    if (activeLines.relPathUOME) {
      traces.push({
        x: dates,
        y: volatilityData.map(d => d.uomeVolatility),
        name: 'UOME Volatility',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#8B4789', width: 2.5 },
        marker: { 
          color: '#8B4789', 
          size: 6,
          line: { color: 'white', width: 1 }
        },
        yaxis: 'y2',
        hovertemplate: '<b>UOME Volatility</b><br>%{y:.3f}%<extra></extra>',
      });
    }
    
    // Layer 0: KOLMO Deviation - Dotted Line
    if (activeLines.kolmoDeviation) {
      traces.push({
        x: dates,
        y: filteredData.map(d => d.kolmoDeviation),
        name: 'KOLMO Deviation',
        type: 'scatter',
        mode: 'lines',
        line: { color: '#8B5A7D', width: 2.5, dash: 'dot' },
        yaxis: 'y',
        hovertemplate: '<b>KOLMO Deviation</b><br>%{y:.2f}σ<extra></extra>',
      });
    }
    
    const layout = {
      autosize: true,
      height: 600,
      paper_bgcolor: 'rgba(255,255,255,1)',
      plot_bgcolor: 'rgba(255,255,255,1)',
      margin: { l: 80, r: 80, t: 40, b: 80 },
      hovermode: 'x unified',
      showlegend: true,
      legend: {
        orientation: 'h',
        yanchor: 'bottom',
        y: 1.02,
        xanchor: 'center',
        x: 0.5,
        bgcolor: 'rgba(255,255,255,0.8)',
        bordercolor: '#E5E7EB',
        borderwidth: 1,
        itemwidth: 30,
        tracegroupgap: 0,
      },
      xaxis: {
        title: '',
        showgrid: true,
        gridcolor: '#E5E7EB',
        zeroline: false,
        type: 'date',
      },
      // Y-axis for KOLMO Deviation (hidden labels)
      yaxis: {
        title: '',
        showgrid: true,
        gridcolor: '#E5E7EB',
        zeroline: true,
        zerolinecolor: '#9CA3AF',
        range: yAxisDomains.deviation,
        showticklabels: false,
        side: 'left',
      },
      // Y-axis for Volatility Rates
      yaxis2: {
        title: { text: 'Volatility (%)', font: { size: 12, color: '#6B7280' } },
        showgrid: false,
        zeroline: true,
        zerolinecolor: '#9CA3AF',
        range: yAxisDomains.volatility,
        overlaying: 'y',
        side: 'left',
        position: 0,
      },
      // Y-axis for General Rates (hidden labels, stacked expanded)
      yaxis3: {
        title: '',
        showgrid: false,
        zeroline: false,
        range: yAxisDomains.general,
        showticklabels: false,
        overlaying: 'y',
        side: 'right',
      },
    };
    
    const config = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    };
    
    Plotly.newPlot(plotRef.current, traces, layout, config);
    
    return () => {
      if (plotRef.current) {
        Plotly.purge(plotRef.current);
      }
    };
  }, [filteredData, volatilityData, activeLines, yAxisDomains]);
  
  // Toggle functions
  const toggleLine = (key: string) => {
    setActiveLines(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));
  };
  
  const toggleAll = () => {
    const allActive = Object.values(activeLines).every(v => v);
    const newState = !allActive;
    setActiveLines({
      kolmoDeviation: newState,
      relPathME4U: newState,
      relPathIOU2: newState,
      relPathUOME: newState,
      me4uRate: newState,
      iou2Rate: newState,
      uomeRate: newState,
    });
  };
  
  const toggleBothLayers = (currency: 'ME4U' | 'IOU2' | 'UOME') => {
    const relKey = `relPath${currency}` as keyof typeof activeLines;
    const rateKey = `${currency.toLowerCase()}Rate` as keyof typeof activeLines;
    const bothActive = activeLines[relKey] && activeLines[rateKey];
    
    setActiveLines(prev => ({
      ...prev,
      [relKey]: !bothActive,
      [rateKey]: !bothActive,
    }));
  };
  
  const toggleRelativePaths = () => {
    const allActive = activeLines.relPathME4U && activeLines.relPathIOU2 && activeLines.relPathUOME;
    setActiveLines(prev => ({
      ...prev,
      relPathME4U: !allActive,
      relPathIOU2: !allActive,
      relPathUOME: !allActive,
    }));
  };
  
  const toggleCurrency = () => {
    const allActive = activeLines.me4uRate && activeLines.iou2Rate && activeLines.uomeRate;
    setActiveLines(prev => ({
      ...prev,
      me4uRate: !allActive,
      iou2Rate: !allActive,
      uomeRate: !allActive,
    }));
  };
  
  // Convert index to date string
  const indexToDate = (index: number): string => {
    return allData[index]?.date || '';
  };
  
  // Convert date string to index
  const dateToIndex = (dateStr: string): number => {
    const index = allData.findIndex(d => d.date === dateStr);
    return index >= 0 ? index : 0;
  };

  return (
    <div className="min-h-screen p-4 md:p-8" style={{ backgroundColor: '#F0EBCE' }}>
      <div className="max-w-[1800px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl text-gray-900 mb-2">KOLMO Analytics</h1>
          <p className="text-gray-600">Daily payment system performance tracking and analysis</p>
        </div>
        
        {/* Current Information Bar */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {/* IOU2 Volatility */}
          <div 
            className="rounded-xl p-4 border border-gray-200 shadow-sm"
            style={{ backgroundColor: winner === 'IOU2' ? 'rgba(0, 135, 108, 0.1)' : 'white' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#5B4E7C' }} />
              <h3 className="text-sm text-gray-600">IOU2 Volatility</h3>
            </div>
            <div className="text-2xl font-semibold text-gray-900 mb-1">
              {currentData.iou2Volatility >= 0 ? '+' : ''}{currentData.iou2Volatility.toFixed(3)}%
            </div>
            <div className="text-xs text-gray-600">
              {currentData.date}
            </div>
          </div>
          
          {/* ME4U Volatility */}
          <div 
            className="rounded-xl p-4 border border-gray-200 shadow-sm"
            style={{ backgroundColor: winner === 'ME4U' ? 'rgba(0, 135, 108, 0.1)' : 'white' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#C08060' }} />
              <h3 className="text-sm text-gray-600">ME4U Volatility</h3>
            </div>
            <div className="text-2xl font-semibold text-gray-900 mb-1">
              {currentData.me4uVolatility >= 0 ? '+' : ''}{currentData.me4uVolatility.toFixed(3)}%
            </div>
            <div className="text-xs text-gray-600">
              {currentData.date}
            </div>
          </div>
          
          {/* UOME Volatility */}
          <div 
            className="rounded-xl p-4 border border-gray-200 shadow-sm"
            style={{ backgroundColor: winner === 'UOME' ? 'rgba(0, 135, 108, 0.1)' : 'white' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#8B4789' }} />
              <h3 className="text-sm text-gray-600">UOME Volatility</h3>
            </div>
            <div className="text-2xl font-semibold text-gray-900 mb-1">
              {currentData.uomeVolatility >= 0 ? '+' : ''}{currentData.uomeVolatility.toFixed(3)}%
            </div>
            <div className="text-xs text-gray-600">
              {currentData.date}
            </div>
          </div>
          
          {/* KOLMO Deviation */}
          <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#8B5A7D' }} />
              <h3 className="text-sm text-gray-600">KOLMO Deviation</h3>
            </div>
            <div className="text-2xl font-semibold text-gray-900 mb-1">
              {currentData.kolmoDeviation.toFixed(2)}σ
            </div>
            <div className="text-xs text-gray-600">
              {currentData.date}
            </div>
          </div>
        </div>
        
        {/* Main Chart */}
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-200 mb-6">
          <h2 className="text-xl text-gray-900 mb-4">KOLMO Chart - Multi-Layer Analysis</h2>
          
          <div ref={plotRef} className="w-full" />
          
          {/* Time Range Bar */}
          <div className="mt-6 bg-gray-50 rounded-xl p-4 border border-gray-200">
            <h3 className="text-sm text-gray-800 mb-3">Time Range Selector</h3>
            
            {/* Date Inputs */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="block text-xs text-gray-600 mb-1">Start Date</label>
                <input
                  type="date"
                  value={indexToDate(startIndex)}
                  min={allData[0]?.date}
                  max={allData[allData.length - 1]?.date}
                  onChange={(e) => {
                    const newIndex = dateToIndex(e.target.value);
                    if (newIndex < endIndex) {
                      setStartIndex(newIndex);
                    }
                  }}
                  className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded bg-white text-gray-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">End Date</label>
                <input
                  type="date"
                  value={indexToDate(endIndex)}
                  min={allData[0]?.date}
                  max={allData[allData.length - 1]?.date}
                  onChange={(e) => {
                    const newIndex = dateToIndex(e.target.value);
                    if (newIndex > startIndex) {
                      setEndIndex(newIndex);
                    }
                  }}
                  className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded bg-white text-gray-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
            
            {/* Interactive Timeline */}
            <div className="bg-white rounded-lg border border-gray-300 p-4">
              <div className="flex justify-between text-xs text-gray-600 mb-2">
                <span>July 1, 2021</span>
                <span>Selected: {filteredData.length} days</span>
                <span>Today</span>
              </div>
              
              {/* Timeline Container */}
              <div className="relative h-16 mb-2">
                {/* Full Timeline Background - Each day as a segment */}
                <div className="absolute inset-0 flex gap-[1px]">
                  {allData.map((_, i) => (
                    <div
                      key={i}
                      className="flex-1 bg-gray-200 hover:bg-gray-300 cursor-pointer transition-colors"
                      onClick={() => {
                        // Click to center range on this point
                        const rangeSize = endIndex - startIndex;
                        const halfRange = Math.floor(rangeSize / 2);
                        let newStart = Math.max(0, i - halfRange);
                        let newEnd = Math.min(allData.length - 1, i + halfRange);
                        
                        // Adjust if we hit boundaries
                        if (newEnd - newStart < rangeSize) {
                          if (newStart === 0) {
                            newEnd = Math.min(allData.length - 1, rangeSize);
                          } else if (newEnd === allData.length - 1) {
                            newStart = Math.max(0, allData.length - 1 - rangeSize);
                          }
                        }
                        
                        setStartIndex(newStart);
                        setEndIndex(newEnd);
                      }}
                      title={allData[i].date}
                    />
                  ))}
                </div>
                
                {/* Selected Range Highlight */}
                <div
                  className="absolute top-0 bottom-0 bg-blue-500 pointer-events-none rounded"
                  style={{
                    left: `${(startIndex / (allData.length - 1)) * 100}%`,
                    width: `${((endIndex - startIndex) / (allData.length - 1)) * 100}%`,
                    opacity: 0.4,
                  }}
                />
                
                {/* Left Handle */}
                <div
                  className="absolute top-0 bottom-0 w-4 bg-blue-600 cursor-ew-resize hover:bg-blue-700 transition-colors rounded-l flex items-center justify-center group shadow-lg z-10"
                  style={{
                    left: `${(startIndex / (allData.length - 1)) * 100}%`,
                    transform: 'translateX(-50%)',
                  }}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    
                    const handleMouseMove = (e: MouseEvent) => {
                      const container = document.querySelector('.relative.h-16');
                      if (!container) return;
                      
                      const rect = container.getBoundingClientRect();
                      const offsetX = e.clientX - rect.left;
                      const percentage = Math.max(0, Math.min(1, offsetX / rect.width));
                      const newStart = Math.round(percentage * (allData.length - 1));
                      
                      if (newStart < endIndex) {
                        setStartIndex(newStart);
                      }
                    };
                    
                    const handleMouseUp = () => {
                      document.removeEventListener('mousemove', handleMouseMove);
                      document.removeEventListener('mouseup', handleMouseUp);
                    };
                    
                    document.addEventListener('mousemove', handleMouseMove);
                    document.addEventListener('mouseup', handleMouseUp);
                  }}
                >
                  <div className="w-1 h-8 bg-white opacity-80 group-hover:opacity-100 rounded" />
                </div>
                
                {/* Right Handle */}
                <div
                  className="absolute top-0 bottom-0 w-4 bg-blue-600 cursor-ew-resize hover:bg-blue-700 transition-colors rounded-r flex items-center justify-center group shadow-lg z-10"
                  style={{
                    left: `${(endIndex / (allData.length - 1)) * 100}%`,
                    transform: 'translateX(-50%)',
                  }}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    
                    const handleMouseMove = (e: MouseEvent) => {
                      const container = document.querySelector('.relative.h-16');
                      if (!container) return;
                      
                      const rect = container.getBoundingClientRect();
                      const offsetX = e.clientX - rect.left;
                      const percentage = Math.max(0, Math.min(1, offsetX / rect.width));
                      const newEnd = Math.round(percentage * (allData.length - 1));
                      
                      if (newEnd > startIndex) {
                        setEndIndex(newEnd);
                      }
                    };
                    
                    const handleMouseUp = () => {
                      document.removeEventListener('mousemove', handleMouseMove);
                      document.removeEventListener('mouseup', handleMouseUp);
                    };
                    
                    document.addEventListener('mousemove', handleMouseMove);
                    document.addEventListener('mouseup', handleMouseUp);
                  }}
                >
                  <div className="w-1 h-8 bg-white opacity-80 group-hover:opacity-100 rounded" />
                </div>
              </div>
              
              {/* Timeline Labels */}
              <div className="relative h-6">
                {Array.from({ length: 11 }).map((_, i) => {
                  const index = Math.round((i / 10) * (allData.length - 1));
                  return (
                    <div
                      key={i}
                      className="absolute flex flex-col items-center"
                      style={{
                        left: `${(index / (allData.length - 1)) * 100}%`,
                        transform: 'translateX(-50%)',
                      }}
                    >
                      <div className="w-px h-2 bg-gray-400" />
                      <span className="text-[9px] text-gray-600 mt-0.5 whitespace-nowrap">
                        {allData[index]?.date.split('-').slice(1).join('/')}
                      </span>
                    </div>
                  );
                })}
              </div>
              
              {/* Quick Selection Buttons */}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => {
                    setStartIndex(0);
                    setEndIndex(allData.length - 1);
                  }}
                  className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                >
                  All Time
                </button>
                <button
                  onClick={() => {
                    setStartIndex(Math.max(0, allData.length - 365));
                    setEndIndex(allData.length - 1);
                  }}
                  className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                >
                  Last Year
                </button>
                <button
                  onClick={() => {
                    setStartIndex(Math.max(0, allData.length - 180));
                    setEndIndex(allData.length - 1);
                  }}
                  className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                >
                  Last 6 Months
                </button>
                <button
                  onClick={() => {
                    setStartIndex(Math.max(0, allData.length - 90));
                    setEndIndex(allData.length - 1);
                  }}
                  className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                >
                  Last 90 Days
                </button>
                <button
                  onClick={() => {
                    setStartIndex(Math.max(0, allData.length - 30));
                    setEndIndex(allData.length - 1);
                  }}
                  className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                >
                  Last 30 Days
                </button>
              </div>
            </div>
            
            <div className="mt-3 text-xs text-gray-600 text-center">
              Showing {filteredData.length} days from {allData.length} total days ({filteredData[0]?.date || ''} - {filteredData[filteredData.length - 1]?.date || ''})
            </div>
          </div>
        </div>
        
        {/* Analysis Tool - 3x4 Grid */}
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-200 mb-6">
          <h3 className="text-lg text-gray-900 mb-4">Analysis Tool</h3>
          
          <div className="grid grid-cols-4 gap-3">
            {/* Row 1, Column 1: Eye/EyeOff & KOLMO Deviation */}
            <div className="flex gap-2">
              <button
                onClick={toggleAll}
                className={`flex-1 px-3 py-3 rounded-lg border-2 transition-all flex items-center justify-center ${
                  Object.values(activeLines).every(v => v)
                    ? 'bg-white border-gray-400 text-gray-700'
                    : 'bg-gray-200 border-gray-300 text-gray-500'
                }`}
                title={Object.values(activeLines).every(v => v) ? 'Hide All' : 'Show All'}
              >
                {Object.values(activeLines).every(v => v) ? (
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </button>
              <button
                onClick={() => toggleLine('kolmoDeviation')}
                className={`flex-[2] px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                  activeLines.kolmoDeviation
                    ? 'bg-white text-purple-700'
                    : 'bg-gray-200 text-gray-600'
                }`}
                style={{ borderColor: activeLines.kolmoDeviation ? '#8B5A7D' : '#d1d5db' }}
              >
                KOLMO deviation
              </button>
            </div>
            
            {/* Row 1, Column 2: IOU2 & Rel. Path IOU2 Tumbler */}
            <button
              onClick={() => toggleBothLayers('IOU2')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.relPathIOU2 && activeLines.iou2Rate
                  ? 'bg-white text-green-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.relPathIOU2 && activeLines.iou2Rate ? '#00876C' : '#d1d5db' }}
            >
              IOU2 & Rel. Path IOU2
            </button>
            
            {/* Row 1, Column 3: ME4U & Rel. Path ME4U Tumbler */}
            <button
              onClick={() => toggleBothLayers('ME4U')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.relPathME4U && activeLines.me4uRate
                  ? 'bg-white text-red-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.relPathME4U && activeLines.me4uRate ? '#D95F59' : '#d1d5db' }}
            >
              ME4U & Rel. Path ME4U
            </button>
            
            {/* Row 1, Column 4: UOME & Rel. Path UOME Tumbler */}
            <button
              onClick={() => toggleBothLayers('UOME')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.relPathUOME && activeLines.uomeRate
                  ? 'bg-white text-yellow-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.relPathUOME && activeLines.uomeRate ? '#A89F3C' : '#d1d5db' }}
            >
              UOME & Rel. Path UOME
            </button>
            
            {/* Row 2, Column 1: Relative Path */}
            <button
              onClick={toggleRelativePaths}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.relPathME4U && activeLines.relPathIOU2 && activeLines.relPathUOME
                  ? 'bg-white border-gray-600 text-gray-800'
                  : 'bg-gray-200 border-gray-300 text-gray-600'
              }`}
            >
              Relative Path
            </button>
            
            {/* Row 2, Column 2: Rel. Path IOU2 */}
            <button
              onClick={() => toggleLine('relPathIOU2')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.relPathIOU2
                  ? 'bg-white text-purple-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.relPathIOU2 ? '#5B4E7C' : '#d1d5db' }}
            >
              Rel. Path IOU2
            </button>
            
            {/* Row 2, Column 3: Rel. Path ME4U */}
            <button
              onClick={() => toggleLine('relPathME4U')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.relPathME4U
                  ? 'bg-white text-orange-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.relPathME4U ? '#C08060' : '#d1d5db' }}
            >
              Rel. Path ME4U
            </button>
            
            {/* Row 2, Column 4: Rel. Path UOME */}
            <button
              onClick={() => toggleLine('relPathUOME')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.relPathUOME
                  ? 'bg-white text-pink-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.relPathUOME ? '#8B4789' : '#d1d5db' }}
            >
              Rel. Path UOME
            </button>
            
            {/* Row 3, Column 1: Currency */}
            <button
              onClick={toggleCurrency}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.me4uRate && activeLines.iou2Rate && activeLines.uomeRate
                  ? 'bg-white border-gray-600 text-gray-800'
                  : 'bg-gray-200 border-gray-300 text-gray-600'
              }`}
            >
              Currency
            </button>
            
            {/* Row 3, Column 2: IOU2 */}
            <button
              onClick={() => toggleLine('iou2Rate')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.iou2Rate
                  ? 'bg-white text-green-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.iou2Rate ? '#00876C' : '#d1d5db' }}
            >
              IOU2
            </button>
            
            {/* Row 3, Column 3: ME4U */}
            <button
              onClick={() => toggleLine('me4uRate')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.me4uRate
                  ? 'bg-white text-red-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.me4uRate ? '#D95F59' : '#d1d5db' }}
            >
              ME4U
            </button>
            
            {/* Row 3, Column 4: UOME */}
            <button
              onClick={() => toggleLine('uomeRate')}
              className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                activeLines.uomeRate
                  ? 'bg-white text-yellow-700'
                  : 'bg-gray-200 text-gray-600'
              }`}
              style={{ borderColor: activeLines.uomeRate ? '#A89F3C' : '#d1d5db' }}
            >
              UOME
            </button>
          </div>
        </div>
        
        {/* Data Table */}
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-200">
          <h3 className="text-lg text-gray-900 mb-4">Data Table - Selected Period</h3>
          
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b-2 border-gray-300">
                  <th className="text-left py-2 px-3 text-gray-700 font-semibold">Date</th>
                  <th className="text-left py-2 px-3 text-gray-700 font-semibold">Winner</th>
                  <th className="text-right py-2 px-3 text-gray-700 font-semibold">ME4U (Rate)</th>
                  <th className="text-right py-2 px-3 text-gray-700 font-semibold">IOU2 (Rate)</th>
                  <th className="text-right py-2 px-3 text-gray-700 font-semibold">UOME (Rate)</th>
                  <th className="text-right py-2 px-3 text-gray-700 font-semibold">RelPath ME4U</th>
                  <th className="text-right py-2 px-3 text-gray-700 font-semibold">RelPath IOU2</th>
                  <th className="text-right py-2 px-3 text-gray-700 font-semibold">RelPath UOME</th>
                  <th className="text-right py-2 px-3 text-gray-700 font-semibold">Kolmo Dev %</th>
                  <th className="text-left py-2 px-3 text-gray-700 font-semibold">Trace ID</th>
                </tr>
              </thead>
              <tbody>
                {volatilityData.slice().reverse().map((row, index) => (
                  <tr 
                    key={index} 
                    className="border-b border-gray-200 hover:bg-gray-50 transition-colors"
                    style={{ 
                      backgroundColor: row.winner === 'IOU2' 
                        ? 'rgba(0, 135, 108, 0.05)' 
                        : row.winner === 'ME4U' 
                        ? 'rgba(192, 128, 96, 0.05)' 
                        : 'rgba(139, 71, 137, 0.05)' 
                    }}
                  >
                    <td className="py-2 px-3 text-gray-800">{row.date}</td>
                    <td className="py-2 px-3">
                      <span 
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                        style={{
                          backgroundColor: row.winner === 'IOU2' ? '#5B4E7C' : row.winner === 'ME4U' ? '#C08060' : '#8B4789',
                          color: 'white'
                        }}
                      >
                        {row.winner}
                        <TrendingUp className="w-3 h-3" />
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right text-gray-800">{row.me4uRate.toFixed(4)}</td>
                    <td className="py-2 px-3 text-right text-gray-800">{row.iou2Rate.toFixed(4)}</td>
                    <td className="py-2 px-3 text-right text-gray-800">{row.uomeRate.toFixed(4)}</td>
                    <td className="py-2 px-3 text-right font-medium" style={{ color: '#C08060' }}>
                      {row.me4uVolatility >= 0 ? '+' : ''}{row.me4uVolatility.toFixed(3)}%
                    </td>
                    <td className="py-2 px-3 text-right font-medium" style={{ color: '#5B4E7C' }}>
                      {row.iou2Volatility >= 0 ? '+' : ''}{row.iou2Volatility.toFixed(3)}%
                    </td>
                    <td className="py-2 px-3 text-right font-medium" style={{ color: '#8B4789' }}>
                      {row.uomeVolatility >= 0 ? '+' : ''}{row.uomeVolatility.toFixed(3)}%
                    </td>
                    <td className="py-2 px-3 text-right font-medium" style={{ color: '#8B5A7D' }}>
                      {row.kolmoDeviation.toFixed(2)}σ
                    </td>
                    <td className="py-2 px-3 text-gray-600 font-mono">{row.traceId}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <div className="mt-3 text-xs text-gray-600 text-center">
            Showing all {filteredData.length} rows in selected period
          </div>
        </div>
      </div>
    </div>
  );
}