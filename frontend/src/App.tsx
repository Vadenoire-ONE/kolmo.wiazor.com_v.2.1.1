import React, {
  useState,
  useMemo,
  useEffect,
  useRef,
} from "react";
import Plotly from "plotly.js-dist-min";
import { Eye, EyeOff, TrendingUp } from "lucide-react";

// Data type
interface KolmoDataPoint {
  date: string;
  dateObj: Date;
  kolmoDeviation: number;
  relPathME4U: number;
  relPathIOU2: number;
  relPathUOME: number;
  volME4U: number;
  volIOU2: number;
  volUOME: number;
  winner: string;
  traceId?: string;
}

export default function App() {
  const [allData, setAllData] = useState<KolmoDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [showDataInput, setShowDataInput] = useState(false);
  const [jsonInput, setJsonInput] = useState("");
  const plotRef = useRef<HTMLDivElement>(null);

  // Date range state (indices)
  const [startIndex, setStartIndex] = useState(0);
  const [endIndex, setEndIndex] = useState(0);

  // Fetch data from GitHub on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Local file served by Vite middleware (data/export/kolmo_history.json)
        const localUrl = "/api/kolmo_history.json";

        // Direct GitHub URL (fallback)
        const directUrl =
          "https://raw.githubusercontent.com/Vadenoire-ONE/kolmo.wiazor.com_v.2.1.1/main/data/export/kolmo_history.json";

        // Try local file first, then GitHub, then CORS proxies
        const urls = [
          localUrl, // Local file via Vite dev server
          directUrl, // Direct GitHub
          `https://corsproxy.io/?${encodeURIComponent(directUrl)}`, // CORS proxy 1
          `https://api.allorigins.win/raw?url=${encodeURIComponent(directUrl)}`, // CORS proxy 2
        ];

        let response = null;
        let lastError = null;
        let successUrl = null;

        for (const url of urls) {
          try {
            console.log("Trying to fetch from:", url);
            const res = await fetch(url, {
              cache: "no-cache",
              headers: {
                "Cache-Control": "no-cache",
              },
            });
            if (res.ok) {
              response = res;
              successUrl = url;
              console.log("✓ Successfully fetched from:", url);
              break;
            }
            lastError = `Status ${res.status}: ${res.statusText}`;
            console.log("✗ Failed:", url, lastError);
          } catch (err) {
            lastError =
              err instanceof Error ? err.message : String(err);
            console.log("✗ Error:", url, lastError);
          }
        }

        if (!response || !response.ok) {
          // Use mock data as fallback
          console.warn(
            "Could not fetch from GitHub, using mock data. Error:",
            lastError,
          );

          // Generate mock data
          const startDate = new Date("2021-07-01");
          const today = new Date();
          const mockData: KolmoDataPoint[] = [];

          let currentDate = new Date(startDate);
          let index = 0;

          while (currentDate <= today) {
            const dateStr = currentDate
              .toISOString()
              .split("T")[0];

            // Generate realistic data
            const kolmoDeviation =
              Math.sin(index * 0.02) * 5 +
              (Math.random() - 0.5) * 3;

            const volME4U = 0.25 + Math.random() * 0.1;
            const volIOU2 = 0.35 + Math.random() * 0.1;
            const volUOME = 0.4 + Math.random() * 0.1;

            const relPathME4U =
              100 + index * 0.05 + Math.random() * 2;
            const relPathIOU2 =
              100 + index * 0.04 + Math.random() * 1.8;
            const relPathUOME =
              100 + index * 0.045 + Math.random() * 1.9;

            // Determine winner
            const relPaths = {
              ME4U: relPathME4U,
              IOU2: relPathIOU2,
              UOME: relPathUOME,
            };
            const winner = Object.entries(relPaths).reduce(
              (a, b) => (a[1] > b[1] ? a : b),
            )[0];

            mockData.push({
              date: dateStr,
              dateObj: new Date(currentDate),
              kolmoDeviation,
              relPathME4U,
              relPathIOU2,
              relPathUOME,
              volME4U,
              volIOU2,
              volUOME,
              winner,
              traceId: `TRACE-${index.toString().padStart(6, "0")}`,
            });

            currentDate.setDate(currentDate.getDate() + 1);
            index++;
          }

          setAllData(mockData);

          // Set initial date range: last year by default
          const dataLength = mockData.length;
          setStartIndex(Math.max(0, dataLength - 365));
          setEndIndex(dataLength - 1);

          setIsLoading(false);
          setError("GitHub file not found. Using mock data.");
          return;
        }

        console.log(
          "Successfully loaded data from:",
          successUrl,
        );
        const jsonData = await response.json();

        if (!Array.isArray(jsonData) || jsonData.length === 0) {
          throw new Error(
            "Invalid data format: Expected non-empty array",
          );
        }

        // Transform data to match our interface
        const transformedData: KolmoDataPoint[] = jsonData.map(
          (row: any, index: number) => ({
            date: row.date || row.observation_date || "",
            dateObj: new Date(
              row.date || row.observation_date || "",
            ),
            kolmoDeviation: Number(row.kolmo_deviation || 0),
            relPathME4U: Number(row.relpath_me4u || 0),
            relPathIOU2: Number(row.relpath_iou2 || 0),
            relPathUOME: Number(row.relpath_uome || 0),
            volME4U: Number(row.vol_me4u || 0),
            volIOU2: Number(row.vol_iou2 || 0),
            volUOME: Number(row.vol_uome || 0),
            winner: row.winner || "N/A",
            traceId:
              row.trace_id ||
              `TRACE-${index.toString().padStart(6, "0")}`,
          }),
        );

        if (transformedData.length === 0) {
          throw new Error(
            "No valid data points found in the JSON file",
          );
        }

        setAllData(transformedData);

        // Set initial date range: last year by default
        const dataLength = transformedData.length;
        setStartIndex(Math.max(0, dataLength - 365));
        setEndIndex(dataLength - 1);

        setIsLoading(false);
      } catch (err) {
        console.error("Error fetching data:", err);
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load data",
        );
        setIsLoading(false);
      }
    };

    fetchData();
  }, [retryKey]);

  // Active layers state
  const [activeLines, setActiveLines] = useState({
    kolmoDeviation: true,
    relPathME4U: true,
    relPathIOU2: true,
    relPathUOME: true,
    volME4U: true,
    volIOU2: true,
    volUOME: true,
  });

  // Get filtered data based on range
  const filteredData = useMemo(() => {
    return allData.slice(startIndex, endIndex + 1);
  }, [allData, startIndex, endIndex]);

  // Get current (last) values
  const currentData =
    filteredData[filteredData.length - 1] ||
    allData[allData.length - 1];

  // Determine winner - only if currentData exists
  const winner = currentData
    ? (() => {
        const relPaths = {
          IOU2: currentData.relPathIOU2,
          ME4U: currentData.relPathME4U,
          UOME: currentData.relPathUOME,
        };
        return Object.entries(relPaths).reduce((a, b) =>
          a[1] > b[1] ? a : b,
        )[0];
      })()
    : "N/A";

  // Calculate Y-axis domains based on extreme values in filtered data
  const yAxisDomains = useMemo(() => {
    // KOLMO Deviation domain
    const kolmoValues = filteredData.map(
      (d) => d.kolmoDeviation,
    );
    const kolmoMin = Math.min(...kolmoValues);
    const kolmoMax = Math.max(...kolmoValues);
    const kolmoPadding = (kolmoMax - kolmoMin) * 0.1;

    // Relative Rates domain
    const relativeValues = filteredData.flatMap((d) => [
      d.relPathME4U,
      d.relPathIOU2,
      d.relPathUOME,
    ]);
    const relativeMin = Math.min(...relativeValues);
    const relativeMax = Math.max(...relativeValues);
    const relativePadding = (relativeMax - relativeMin) * 0.1;

    // Volatility domain
    const volatilityValues = filteredData.flatMap((d) => [
      d.volME4U,
      d.volIOU2,
      d.volUOME,
    ]);
    const volatilityMin = Math.min(...volatilityValues);
    const volatilityMax = Math.max(...volatilityValues);
    const volatilityPadding =
      (volatilityMax - volatilityMin) * 0.15;

    return {
      deviation: [
        kolmoMin - kolmoPadding,
        kolmoMax + kolmoPadding,
      ],
      relative: [
        relativeMin - relativePadding,
        relativeMax + relativePadding,
      ],
      volatility: [
        volatilityMin - volatilityPadding,
        volatilityMax + volatilityPadding,
      ],
    };
  }, [filteredData]);

  // Render Plotly chart
  useEffect(() => {
    if (!plotRef.current) return;

    const dates = filteredData.map((d) => d.dateObj);

    const traces: any[] = [];

    // Layer B: VOLATILITY MARKERS - Scatter Plots with Distinct Marker Shapes
    if (activeLines.volME4U) {
      traces.push({
        x: dates,
        y: filteredData.map((d) => d.volME4U),
        name: "Volatility ME4U",
        type: "scatter",
        mode: "lines",
        line: {
          color: "rgba(192, 128, 96, 0.6)",
          width: 2,
          shape: "hv",
        },
        yaxis: "y3",
        hovertemplate:
          "<b>Vol. ME4U</b><br>%{y:.4f}<extra></extra>",
      });
    }

    if (activeLines.volIOU2) {
      traces.push({
        x: dates,
        y: filteredData.map((d) => d.volIOU2),
        name: "Volatility IOU2",
        type: "scatter",
        mode: "lines",
        line: {
          color: "rgba(91, 78, 124, 0.575)",
          width: 2,
          shape: "hv",
        },
        yaxis: "y3",
        hovertemplate:
          "<b>Vol. IOU2</b><br>%{y:.4f}<extra></extra>",
      });
    }

    if (activeLines.volUOME) {
      traces.push({
        x: dates,
        y: filteredData.map((d) => d.volUOME),
        name: "Volatility UOME",
        type: "scatter",
        mode: "lines",
        line: {
          color: "rgba(139, 71, 137, 0.55)",
          width: 2,
          shape: "hv",
        },
        yaxis: "y3",
        hovertemplate:
          "<b>Vol. UOME</b><br>%{y:.4f}<extra></extra>",
      });
    }

    // Layer A: RELATIVE RATES - Line Charts (0% transparency)
    if (activeLines.relPathME4U) {
      traces.push({
        x: dates,
        y: filteredData.map((d) => d.relPathME4U),
        name: "Rel. Path ME4U",
        type: "scatter",
        mode: "lines",
        line: { color: "#C08060", width: 3 },
        yaxis: "y2",
        hovertemplate:
          "<b>Rel. Path ME4U</b><br>%{y:.2f}%<extra></extra>",
      });
    }

    if (activeLines.relPathIOU2) {
      traces.push({
        x: dates,
        y: filteredData.map((d) => d.relPathIOU2),
        name: "Rel. Path IOU2",
        type: "scatter",
        mode: "lines",
        line: { color: "#5B4E7C", width: 3 },
        yaxis: "y2",
        hovertemplate:
          "<b>Rel. Path IOU2</b><br>%{y:.2f}%<extra></extra>",
      });
    }

    if (activeLines.relPathUOME) {
      traces.push({
        x: dates,
        y: filteredData.map((d) => d.relPathUOME),
        name: "Rel. Path UOME",
        type: "scatter",
        mode: "lines",
        line: { color: "#8B4789", width: 3 },
        yaxis: "y2",
        hovertemplate:
          "<b>Rel. Path UOME</b><br>%{y:.2f}%<extra></extra>",
      });
    }

    // Layer 0: KOLMO Deviation - Dotted Line
    if (activeLines.kolmoDeviation) {
      traces.push({
        x: dates,
        y: filteredData.map((d) => d.kolmoDeviation),
        name: "KOLMO Deviation",
        type: "scatter",
        mode: "lines",
        line: { color: "#8B5A7D", width: 2.5, dash: "dot" },
        yaxis: "y",
        hovertemplate:
          "<b>KOLMO Deviation</b><br>%{y:.2e}<extra></extra>",
      });
    }

    const layout = {
      autosize: true,
      height: 600,
      paper_bgcolor: "rgba(255,255,255,1)",
      plot_bgcolor: "rgba(255,255,255,1)",
      margin: { l: 80, r: 80, t: 40, b: 80 },
      hovermode: "x unified",
      showlegend: true,
      legend: {
        orientation: "h",
        yanchor: "bottom",
        y: 1.02,
        xanchor: "center",
        x: 0.5,
        bgcolor: "rgba(255,255,255,0.8)",
        bordercolor: "#E5E7EB",
        borderwidth: 1,
        itemwidth: 50,
        tracegroupgap: 10,
        itemsizing: "constant",
        font: { size: 11 },
      },
      xaxis: {
        title: "",
        showgrid: true,
        gridcolor: "#E5E7EB",
        zeroline: false,
        type: "date",
      },
      // Y-axis for KOLMO Deviation (hidden labels)
      yaxis: {
        title: "",
        showgrid: true,
        gridcolor: "#E5E7EB",
        zeroline: true,
        zerolinecolor: "#9CA3AF",
        range: yAxisDomains.deviation,
        showticklabels: false,
        side: "left",
      },
      // Y-axis for Relative Rates
      yaxis2: {
        title: {
          text: "Relative Rates (%)",
          font: { size: 12, color: "#6B7280" },
        },
        showgrid: false,
        zeroline: false,
        range: yAxisDomains.relative,
        overlaying: "y",
        side: "left",
        position: 0,
      },
      // Y-axis for General Rates (hidden labels, stacked expanded)
      yaxis3: {
        title: "",
        showgrid: false,
        zeroline: false,
        range: yAxisDomains.volatility,
        showticklabels: false,
        overlaying: "y",
        side: "right",
      },
    };

    const config = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    };

    Plotly.newPlot(plotRef.current, traces, layout, config);

    return () => {
      if (plotRef.current) {
        Plotly.purge(plotRef.current);
      }
    };
  }, [filteredData, activeLines, yAxisDomains]);

  // Toggle functions
  const toggleLine = (key: string) => {
    setActiveLines((prev) => ({
      ...prev,
      [key]: !prev[key as keyof typeof prev],
    }));
  };

  const toggleAll = () => {
    const allActive = Object.values(activeLines).every(
      (v) => v,
    );
    const newState = !allActive;
    setActiveLines({
      kolmoDeviation: newState,
      relPathME4U: newState,
      relPathIOU2: newState,
      relPathUOME: newState,
      volME4U: newState,
      volIOU2: newState,
      volUOME: newState,
    });
  };

  const toggleBothLayers = (
    currency: "ME4U" | "IOU2" | "UOME",
  ) => {
    const relKey =
      `relPath${currency}` as keyof typeof activeLines;
    const rateKey =
      `${currency.toLowerCase()}Rate` as keyof typeof activeLines;
    const bothActive =
      activeLines[relKey] && activeLines[rateKey];

    setActiveLines((prev) => ({
      ...prev,
      [relKey]: !bothActive,
      [rateKey]: !bothActive,
    }));
  };

  const toggleRelativePaths = () => {
    const allActive =
      activeLines.relPathME4U &&
      activeLines.relPathIOU2 &&
      activeLines.relPathUOME;
    setActiveLines((prev) => ({
      ...prev,
      relPathME4U: !allActive,
      relPathIOU2: !allActive,
      relPathUOME: !allActive,
    }));
  };

  const toggleCurrency = () => {
    const allActive =
      activeLines.volME4U &&
      activeLines.volIOU2 &&
      activeLines.volUOME;
    setActiveLines((prev) => ({
      ...prev,
      volME4U: !allActive,
      volIOU2: !allActive,
      volUOME: !allActive,
    }));
  };

  // Convert index to date string
  const indexToDate = (index: number): string => {
    return allData[index]?.date || "";
  };

  // Convert date string to index
  const dateToIndex = (dateStr: string): number => {
    const index = allData.findIndex((d) => d.date === dateStr);
    return index >= 0 ? index : 0;
  };

  // Handle manual JSON input
  const handleLoadJson = () => {
    try {
      const jsonData = JSON.parse(jsonInput);

      if (!Array.isArray(jsonData) || jsonData.length === 0) {
        alert("Invalid JSON format: Expected non-empty array");
        return;
      }

      // Transform data
      const transformedData: KolmoDataPoint[] = jsonData.map(
        (row: any, index: number) => ({
          date: row.date || row.observation_date || "",
          dateObj: new Date(
            row.date || row.observation_date || "",
          ),
          kolmoDeviation: Number(row.kolmo_deviation || 0),
          relPathME4U: Number(row.relpath_me4u || 0),
          relPathIOU2: Number(row.relpath_iou2 || 0),
          relPathUOME: Number(row.relpath_uome || 0),
          volME4U: Number(row.vol_me4u || 0),
          volIOU2: Number(row.vol_iou2 || 0),
          volUOME: Number(row.vol_uome || 0),
          winner: row.winner || "N/A",
          traceId:
            row.trace_id ||
            `TRACE-${index.toString().padStart(6, "0")}`,
        }),
      );

      setAllData(transformedData);

      const dataLength = transformedData.length;
      setStartIndex(Math.max(0, dataLength - 365));
      setEndIndex(dataLength - 1);

      setError(null);
      setShowDataInput(false);
      setJsonInput("");

      alert(
        `✅ Successfully loaded ${transformedData.length} data points!`,
      );
    } catch (err) {
      alert(
        `❌ Error parsing JSON: ${err instanceof Error ? err.message : "Invalid format"}`,
      );
    }
  };

  return (
    <div
      className="min-h-screen p-4 md:p-8"
      style={{ backgroundColor: "#F0EBCE" }}
    >
      <div className="max-w-[1800px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl text-gray-900 mb-2">
            KOLMO Analytics
          </h1>
          <p className="text-gray-600">
            Daily payment system performance tracking and
            analysis
          </p>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="bg-white rounded-2xl shadow-xl p-12 border border-gray-200 text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mb-4"></div>
            <p className="text-gray-600">
              Loading KOLMO data from GitHub...
            </p>
          </div>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <div className="bg-yellow-50 rounded-2xl shadow-xl p-6 border-2 border-yellow-300 mb-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-lg text-yellow-900 mb-2 font-semibold">
                  ⚠️ Using Mock Data
                </h3>
                <p className="text-yellow-800 text-sm whitespace-pre-line">
                  {error}
                </p>
                <p className="text-yellow-700 text-sm mt-2">
                  The application is working with generated
                  data.
                </p>

                <div className="mt-3 p-3 bg-yellow-100 rounded border border-yellow-400">
                  <p className="text-xs text-yellow-900 font-semibold mb-1">
                    🔍 Manual Data Loading:
                  </p>
                  <ol className="text-xs text-yellow-800 space-y-1 list-decimal list-inside">
                    <li>
                      Click the link below to open your JSON
                      data
                    </li>
                    <li>
                      Copy all the JSON content (Ctrl+A, Ctrl+C)
                    </li>
                    <li>
                      Click "Load Data Manually" button and
                      paste the JSON
                    </li>
                  </ol>
                  <a
                    href="https://raw.githubusercontent.com/Vadenoire-ONE/kolmo.wiazor.com_v.2.1.1/main/data/export/kolmo_history.json"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block mt-2 text-xs text-blue-700 hover:text-blue-900 underline font-medium"
                  >
                    📎 Open your data file (copy the JSON)
                  </a>
                </div>
              </div>
              <div className="ml-4 flex flex-col gap-2">
                <button
                  onClick={() =>
                    setRetryKey((prev) => prev + 1)
                  }
                  className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white text-sm font-medium rounded-lg transition-colors shadow-sm flex items-center gap-2 whitespace-nowrap"
                >
                  🔄 Retry Auto-Load
                </button>
                <button
                  onClick={() => setShowDataInput(true)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors shadow-sm flex items-center gap-2 whitespace-nowrap"
                >
                  📋 Load Data Manually
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Manual Data Input Modal */}
        {showDataInput && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
              <div className="p-6 border-b border-gray-200">
                <h3 className="text-xl font-semibold text-gray-900">
                  Load Data Manually
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  Paste your JSON data from GitHub below
                </p>
              </div>

              <div className="p-6 flex-1 overflow-auto">
                <textarea
                  value={jsonInput}
                  onChange={(e) => setJsonInput(e.target.value)}
                  placeholder='Paste your JSON array here, e.g.: [{"date":"2021-07-01","kolmo_deviation":1.23,...}, ...]'
                  className="w-full h-96 p-4 border-2 border-gray-300 rounded-lg font-mono text-xs focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                />
                <p className="text-xs text-gray-500 mt-2">
                  💡 Tip: Open the GitHub link, press Ctrl+A to
                  select all, Ctrl+C to copy, then paste here
                </p>
              </div>

              <div className="p-6 border-t border-gray-200 flex gap-3 justify-end">
                <button
                  onClick={() => {
                    setShowDataInput(false);
                    setJsonInput("");
                  }}
                  className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 text-sm font-medium rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleLoadJson}
                  disabled={!jsonInput.trim()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Load Data
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Content - only show when data is loaded */}
        {!isLoading && allData.length > 0 && currentData && (
          <>
            {/* Current Information Bar */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              {/* Relative Path IOU2 */}
              <div
                className="rounded-xl p-4 border border-gray-200 shadow-sm"
                style={{
                  backgroundColor:
                    winner === "IOU2"
                      ? "rgba(0, 135, 108, 0.1)"
                      : "white",
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: "#5B4E7C" }}
                  />
                  <h3 className="text-sm text-gray-600">
                    Relative Path IOU2
                  </h3>
                </div>
                <div className="text-2xl font-semibold text-gray-900 mb-1">
                  {currentData.relPathIOU2.toFixed(2)}%
                </div>
                <div className="text-xs text-gray-600">
                  {currentData.date}
                </div>
              </div>

              {/* Relative Path ME4U */}
              <div
                className="rounded-xl p-4 border border-gray-200 shadow-sm"
                style={{
                  backgroundColor:
                    winner === "ME4U"
                      ? "rgba(0, 135, 108, 0.1)"
                      : "white",
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: "#C08060" }}
                  />
                  <h3 className="text-sm text-gray-600">
                    Relative Path ME4U
                  </h3>
                </div>
                <div className="text-2xl font-semibold text-gray-900 mb-1">
                  {currentData.relPathME4U.toFixed(2)}%
                </div>
                <div className="text-xs text-gray-600">
                  {currentData.date}
                </div>
              </div>

              {/* Relative Path UOME */}
              <div
                className="rounded-xl p-4 border border-gray-200 shadow-sm"
                style={{
                  backgroundColor:
                    winner === "UOME"
                      ? "rgba(0, 135, 108, 0.1)"
                      : "white",
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: "#8B4789" }}
                  />
                  <h3 className="text-sm text-gray-600">
                    Relative Path UOME
                  </h3>
                </div>
                <div className="text-2xl font-semibold text-gray-900 mb-1">
                  {currentData.relPathUOME.toFixed(2)}%
                </div>
                <div className="text-xs text-gray-600">
                  {currentData.date}
                </div>
              </div>

              {/* KOLMO Deviation */}
              <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: "#8B5A7D" }}
                  />
                  <h3 className="text-sm text-gray-600">
                    KOLMO Deviation
                  </h3>
                </div>
                <div className="text-2xl font-semibold text-gray-900 mb-1">
                  {currentData.kolmoDeviation.toExponential(2)}
                </div>
                <div className="text-xs text-gray-600">
                  {currentData.date}
                </div>
              </div>
            </div>

            {/* Main Chart */}
            <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-200 mb-6">
              <h2 className="text-xl text-gray-900 mb-4">
                KOLMO Chart - Multi-Layer Analysis
              </h2>

              <div ref={plotRef} className="w-full" />

              {/* Time Range Bar */}
              <div className="mt-6 bg-gray-50 rounded-xl p-4 border border-gray-200">
                <h3 className="text-sm text-gray-800 mb-3">
                  Time Range Selector
                </h3>

                {/* Date Inputs */}
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      Start Date
                    </label>
                    <input
                      type="date"
                      value={indexToDate(startIndex)}
                      min={allData[0]?.date}
                      max={allData[allData.length - 1]?.date}
                      onChange={(e) => {
                        const newIndex = dateToIndex(
                          e.target.value,
                        );
                        if (newIndex < endIndex) {
                          setStartIndex(newIndex);
                        }
                      }}
                      className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded bg-white text-gray-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      End Date
                    </label>
                    <input
                      type="date"
                      value={indexToDate(endIndex)}
                      min={allData[0]?.date}
                      max={allData[allData.length - 1]?.date}
                      onChange={(e) => {
                        const newIndex = dateToIndex(
                          e.target.value,
                        );
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
                    <span>
                      Selected: {filteredData.length} days
                    </span>
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
                            const rangeSize =
                              endIndex - startIndex;
                            const halfRange = Math.floor(
                              rangeSize / 2,
                            );
                            let newStart = Math.max(
                              0,
                              i - halfRange,
                            );
                            let newEnd = Math.min(
                              allData.length - 1,
                              i + halfRange,
                            );

                            // Adjust if we hit boundaries
                            if (newEnd - newStart < rangeSize) {
                              if (newStart === 0) {
                                newEnd = Math.min(
                                  allData.length - 1,
                                  rangeSize,
                                );
                              } else if (
                                newEnd ===
                                allData.length - 1
                              ) {
                                newStart = Math.max(
                                  0,
                                  allData.length -
                                    1 -
                                    rangeSize,
                                );
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
                        transform: "translateX(-50%)",
                      }}
                      onMouseDown={(e) => {
                        e.preventDefault();

                        const handleMouseMove = (
                          e: MouseEvent,
                        ) => {
                          const container =
                            document.querySelector(
                              ".relative.h-16",
                            );
                          if (!container) return;

                          const rect =
                            container.getBoundingClientRect();
                          const offsetX = e.clientX - rect.left;
                          const percentage = Math.max(
                            0,
                            Math.min(1, offsetX / rect.width),
                          );
                          const newStart = Math.round(
                            percentage * (allData.length - 1),
                          );

                          if (newStart < endIndex) {
                            setStartIndex(newStart);
                          }
                        };

                        const handleMouseUp = () => {
                          document.removeEventListener(
                            "mousemove",
                            handleMouseMove,
                          );
                          document.removeEventListener(
                            "mouseup",
                            handleMouseUp,
                          );
                        };

                        document.addEventListener(
                          "mousemove",
                          handleMouseMove,
                        );
                        document.addEventListener(
                          "mouseup",
                          handleMouseUp,
                        );
                      }}
                    >
                      <div className="w-1 h-8 bg-white opacity-80 group-hover:opacity-100 rounded" />
                    </div>

                    {/* Right Handle */}
                    <div
                      className="absolute top-0 bottom-0 w-4 bg-blue-600 cursor-ew-resize hover:bg-blue-700 transition-colors rounded-r flex items-center justify-center group shadow-lg z-10"
                      style={{
                        left: `${(endIndex / (allData.length - 1)) * 100}%`,
                        transform: "translateX(-50%)",
                      }}
                      onMouseDown={(e) => {
                        e.preventDefault();

                        const handleMouseMove = (
                          e: MouseEvent,
                        ) => {
                          const container =
                            document.querySelector(
                              ".relative.h-16",
                            );
                          if (!container) return;

                          const rect =
                            container.getBoundingClientRect();
                          const offsetX = e.clientX - rect.left;
                          const percentage = Math.max(
                            0,
                            Math.min(1, offsetX / rect.width),
                          );
                          const newEnd = Math.round(
                            percentage * (allData.length - 1),
                          );

                          if (newEnd > startIndex) {
                            setEndIndex(newEnd);
                          }
                        };

                        const handleMouseUp = () => {
                          document.removeEventListener(
                            "mousemove",
                            handleMouseMove,
                          );
                          document.removeEventListener(
                            "mouseup",
                            handleMouseUp,
                          );
                        };

                        document.addEventListener(
                          "mousemove",
                          handleMouseMove,
                        );
                        document.addEventListener(
                          "mouseup",
                          handleMouseUp,
                        );
                      }}
                    >
                      <div className="w-1 h-8 bg-white opacity-80 group-hover:opacity-100 rounded" />
                    </div>
                  </div>

                  {/* Timeline Labels */}
                  <div className="relative h-6">
                    {Array.from({ length: 11 }).map((_, i) => {
                      const index = Math.round(
                        (i / 10) * (allData.length - 1),
                      );
                      return (
                        <div
                          key={i}
                          className="absolute flex flex-col items-center"
                          style={{
                            left: `${(index / (allData.length - 1)) * 100}%`,
                            transform: "translateX(-50%)",
                          }}
                        >
                          <div className="w-px h-2 bg-gray-400" />
                          <span className="text-[9px] text-gray-600 mt-0.5 whitespace-nowrap">
                            {allData[index]?.date
                              .split("-")
                              .slice(1)
                              .join("/")}
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
                        setStartIndex(
                          Math.max(0, allData.length - 365),
                        );
                        setEndIndex(allData.length - 1);
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                    >
                      Last Year
                    </button>
                    <button
                      onClick={() => {
                        setStartIndex(
                          Math.max(0, allData.length - 180),
                        );
                        setEndIndex(allData.length - 1);
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                    >
                      Last 6 Months
                    </button>
                    <button
                      onClick={() => {
                        setStartIndex(
                          Math.max(0, allData.length - 90),
                        );
                        setEndIndex(allData.length - 1);
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                    >
                      Last 90 Days
                    </button>
                    <button
                      onClick={() => {
                        setStartIndex(
                          Math.max(0, allData.length - 30),
                        );
                        setEndIndex(allData.length - 1);
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded border border-gray-300 transition-all"
                    >
                      Last 30 Days
                    </button>
                  </div>
                </div>

                <div className="mt-3 text-xs text-gray-600 text-center">
                  Showing {filteredData.length} days from{" "}
                  {allData.length} total days (
                  {filteredData[0]?.date || ""} -{" "}
                  {filteredData[filteredData.length - 1]
                    ?.date || ""}
                  )
                </div>
              </div>
            </div>

            {/* Analysis Tool - 3x4 Grid */}
            <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-200 mb-6">
              <h3 className="text-lg text-gray-900 mb-4">
                Analysis Tool
              </h3>

              <div className="grid grid-cols-4 gap-3">
                {/* Row 1, Column 1: Eye/EyeOff & KOLMO Deviation */}
                <div className="flex gap-2">
                  <button
                    onClick={toggleAll}
                    className={`flex-1 px-3 py-3 rounded-lg border-2 transition-all flex items-center justify-center ${
                      Object.values(activeLines).every((v) => v)
                        ? "bg-white border-gray-400 text-gray-700"
                        : "bg-gray-200 border-gray-300 text-gray-500"
                    }`}
                    title={
                      Object.values(activeLines).every((v) => v)
                        ? "Hide All"
                        : "Show All"
                    }
                  >
                    {Object.values(activeLines).every(
                      (v) => v,
                    ) ? (
                      <EyeOff className="w-5 h-5" />
                    ) : (
                      <Eye className="w-5 h-5" />
                    )}
                  </button>
                  <button
                    onClick={() => toggleLine("kolmoDeviation")}
                    className={`flex-[2] px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                      activeLines.kolmoDeviation
                        ? "bg-white text-purple-700"
                        : "bg-gray-200 text-gray-600"
                    }`}
                    style={{
                      borderColor: activeLines.kolmoDeviation
                        ? "#8B5A7D"
                        : "#d1d5db",
                    }}
                  >
                    KOLMO deviation
                  </button>
                </div>

                {/* Row 1, Column 2: IOU2 & Rel. Path IOU2 Tumbler */}
                <button
                  onClick={() => toggleBothLayers("IOU2")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.relPathIOU2 &&
                    activeLines.volIOU2
                      ? "bg-white text-green-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor:
                      activeLines.relPathIOU2 &&
                      activeLines.volIOU2
                        ? "#00876C"
                        : "#d1d5db",
                  }}
                >
                  IOU2 & Rel. Path IOU2
                </button>

                {/* Row 1, Column 3: ME4U & Rel. Path ME4U Tumbler */}
                <button
                  onClick={() => toggleBothLayers("ME4U")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.relPathME4U &&
                    activeLines.volME4U
                      ? "bg-white text-red-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor:
                      activeLines.relPathME4U &&
                      activeLines.volME4U
                        ? "#D95F59"
                        : "#d1d5db",
                  }}
                >
                  ME4U & Rel. Path ME4U
                </button>

                {/* Row 1, Column 4: UOME & Rel. Path UOME Tumbler */}
                <button
                  onClick={() => toggleBothLayers("UOME")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.relPathUOME &&
                    activeLines.volUOME
                      ? "bg-white text-yellow-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor:
                      activeLines.relPathUOME &&
                      activeLines.volUOME
                        ? "#A89F3C"
                        : "#d1d5db",
                  }}
                >
                  UOME & Rel. Path UOME
                </button>

                {/* Row 2, Column 1: Relative Path */}
                <button
                  onClick={toggleRelativePaths}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.relPathME4U &&
                    activeLines.relPathIOU2 &&
                    activeLines.relPathUOME
                      ? "bg-white border-gray-600 text-gray-800"
                      : "bg-gray-200 border-gray-300 text-gray-600"
                  }`}
                >
                  Relative Path
                </button>

                {/* Row 2, Column 2: Rel. Path IOU2 */}
                <button
                  onClick={() => toggleLine("relPathIOU2")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.relPathIOU2
                      ? "bg-white text-purple-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor: activeLines.relPathIOU2
                      ? "#5B4E7C"
                      : "#d1d5db",
                  }}
                >
                  Rel. Path IOU2
                </button>

                {/* Row 2, Column 3: Rel. Path ME4U */}
                <button
                  onClick={() => toggleLine("relPathME4U")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.relPathME4U
                      ? "bg-white text-orange-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor: activeLines.relPathME4U
                      ? "#C08060"
                      : "#d1d5db",
                  }}
                >
                  Rel. Path ME4U
                </button>

                {/* Row 2, Column 4: Rel. Path UOME */}
                <button
                  onClick={() => toggleLine("relPathUOME")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.relPathUOME
                      ? "bg-white text-pink-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor: activeLines.relPathUOME
                      ? "#8B4789"
                      : "#d1d5db",
                  }}
                >
                  Rel. Path UOME
                </button>

                {/* Row 3, Column 1: Volatility */}
                <button
                  onClick={toggleCurrency}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.volME4U &&
                    activeLines.volIOU2 &&
                    activeLines.volUOME
                      ? "bg-white border-gray-600 text-gray-800"
                      : "bg-gray-200 border-gray-300 text-gray-600"
                  }`}
                >
                  Volatility
                </button>

                {/* Row 3, Column 2: Vol IOU2 */}
                <button
                  onClick={() => toggleLine("volIOU2")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.volIOU2
                      ? "bg-white text-green-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor: activeLines.volIOU2
                      ? "#5B4E7C"
                      : "#d1d5db",
                  }}
                >
                  Vol IOU2
                </button>

                {/* Row 3, Column 3: Vol ME4U */}
                <button
                  onClick={() => toggleLine("volME4U")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.volME4U
                      ? "bg-white text-red-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor: activeLines.volME4U
                      ? "#C08060"
                      : "#d1d5db",
                  }}
                >
                  Vol ME4U
                </button>

                {/* Row 3, Column 4: Vol UOME */}
                <button
                  onClick={() => toggleLine("volUOME")}
                  className={`px-3 py-3 rounded-lg border-2 transition-all text-xs font-medium ${
                    activeLines.volUOME
                      ? "bg-white text-yellow-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                  style={{
                    borderColor: activeLines.volUOME
                      ? "#8B4789"
                      : "#d1d5db",
                  }}
                >
                  Vol UOME
                </button>
              </div>
            </div>

            {/* Data Table */}
            <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-200">
              <h3 className="text-lg text-gray-900 mb-4">
                Data Table - Selected Period
              </h3>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b-2 border-gray-300">
                      <th className="text-left py-2 px-3 text-gray-700 font-semibold">
                        Date
                      </th>
                      <th className="text-left py-2 px-3 text-gray-700 font-semibold">
                        Winner
                      </th>
                      <th className="text-right py-2 px-3 text-gray-700 font-semibold">
                        Vol ME4U
                      </th>
                      <th className="text-right py-2 px-3 text-gray-700 font-semibold">
                        Vol IOU2
                      </th>
                      <th className="text-right py-2 px-3 text-gray-700 font-semibold">
                        Vol UOME
                      </th>
                      <th className="text-right py-2 px-3 text-gray-700 font-semibold">
                        RelPath ME4U
                      </th>
                      <th className="text-right py-2 px-3 text-gray-700 font-semibold">
                        RelPath IOU2
                      </th>
                      <th className="text-right py-2 px-3 text-gray-700 font-semibold">
                        RelPath UOME
                      </th>
                      <th className="text-right py-2 px-3 text-gray-700 font-semibold">
                        Kolmo Dev
                      </th>
                      <th className="text-left py-2 px-3 text-gray-700 font-semibold">
                        Trace ID
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredData
                      .slice()
                      .reverse()
                      .map((row, index) => (
                        <tr
                          key={index}
                          className="border-b border-gray-200 hover:bg-gray-50 transition-colors"
                          style={{
                            backgroundColor:
                              row.winner === "IOU2"
                                ? "rgba(0, 135, 108, 0.05)"
                                : row.winner === "ME4U"
                                  ? "rgba(192, 128, 96, 0.05)"
                                  : "rgba(139, 71, 137, 0.05)",
                          }}
                        >
                          <td className="py-2 px-3 text-gray-800">
                            {row.date}
                          </td>
                          <td className="py-2 px-3">
                            <span
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                              style={{
                                backgroundColor:
                                  row.winner === "IOU2"
                                    ? "#5B4E7C"
                                    : row.winner === "ME4U"
                                      ? "#C08060"
                                      : "#8B4789",
                                color: "white",
                              }}
                            >
                              {row.winner}
                              <TrendingUp className="w-3 h-3" />
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right text-gray-800">
                            {row.volME4U.toFixed(4)}
                          </td>
                          <td className="py-2 px-3 text-right text-gray-800">
                            {row.volIOU2.toFixed(4)}
                          </td>
                          <td className="py-2 px-3 text-right text-gray-800">
                            {row.volUOME.toFixed(4)}
                          </td>
                          <td
                            className="py-2 px-3 text-right font-medium"
                            style={{ color: "#C08060" }}
                          >
                            {row.relPathME4U.toFixed(2)}%
                          </td>
                          <td
                            className="py-2 px-3 text-right font-medium"
                            style={{ color: "#5B4E7C" }}
                          >
                            {row.relPathIOU2.toFixed(2)}%
                          </td>
                          <td
                            className="py-2 px-3 text-right font-medium"
                            style={{ color: "#8B4789" }}
                          >
                            {row.relPathUOME.toFixed(2)}%
                          </td>
                          <td
                            className="py-2 px-3 text-right font-medium"
                            style={{ color: "#8B5A7D" }}
                          >
                            {row.kolmoDeviation.toExponential(
                              2,
                            )}
                          </td>
                          <td className="py-2 px-3 text-gray-600 font-mono">
                            {row.traceId}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-3 text-xs text-gray-600 text-center">
                Showing all {filteredData.length} rows in
                selected period
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}