import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'
import { useAuth } from '../context/AuthContext'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend)

const API = import.meta.env.VITE_API_URL || ''

// ── Speedometer SVG ───────────────────────────────────────────────────────────

function Speedometer({ percentage, level }) {
  const angle = -135 + (percentage / 100) * 270  // -135° (left) to +135° (right)
  const rad = (angle * Math.PI) / 180
  const cx = 60, cy = 60, r = 45
  const nx = cx + r * Math.cos(rad)
  const ny = cy + r * Math.sin(rad)

  const arcColor = level === 'low' ? '#22c55e' : level === 'medium' ? '#f59e0b' : '#ef4444'

  return (
    <svg viewBox="0 0 120 80" className="w-32 h-20 mx-auto">
      {/* Background arc */}
      <path
        d="M 15 75 A 45 45 0 1 1 105 75"
        fill="none" stroke="#374151" strokeWidth="8" strokeLinecap="round"
      />
      {/* Colored arc based on level */}
      <path
        d="M 15 75 A 45 45 0 1 1 105 75"
        fill="none" stroke={arcColor} strokeWidth="8" strokeLinecap="round"
        strokeDasharray={`${(percentage / 100) * 141} 141`}
      />
      {/* Needle */}
      <line
        x1={cx} y1={cy}
        x2={nx} y2={ny}
        stroke="white" strokeWidth="2" strokeLinecap="round"
      />
      <circle cx={cx} cy={cy} r="3" fill="white" />
      <text x={cx} y={75} textAnchor="middle" fill={arcColor} fontSize="10" fontWeight="bold">
        {Math.round(percentage)}%
      </text>
    </svg>
  )
}

// ── Clock card ────────────────────────────────────────────────────────────────

function ClockCard({ clock, isSelected, onClick }) {
  const levelLabel = { low: 'נמוך', medium: 'בינוני', high: 'גבוה' }[clock.risk_level] || clock.risk_level
  const levelColor = { low: 'text-green-400', medium: 'text-yellow-400', high: 'text-red-400' }[clock.risk_level]

  return (
    <div
      onClick={onClick}
      className={`bg-[#1a2333] rounded-xl p-5 cursor-pointer border-2 transition-all
        ${isSelected ? 'border-blue-500 shadow-lg shadow-blue-500/20' : 'border-transparent hover:border-gray-600'}`}
    >
      <div className="mb-3">
        <p className="text-gray-400 text-xs mb-1">תשלום חודשי</p>
        <p className="text-2xl font-bold text-white">
          ₪{Math.round(clock.monthly_payment_initial).toLocaleString('he-IL')}
        </p>
      </div>

      <Speedometer percentage={clock.risk_score_percentage} level={clock.risk_level} />

      <div className="mt-3 text-center">
        <span className={`text-sm font-medium ${levelColor}`}>סיכון {levelLabel}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="bg-[#0f1623] rounded p-2">
          <p className="text-gray-500">סה״כ תשלום</p>
          <p className="text-white font-medium">₪{Math.round(clock.total_payment).toLocaleString('he-IL')}</p>
        </div>
        <div className="bg-[#0f1623] rounded p-2">
          <p className="text-gray-500">עלות ריבית</p>
          <p className="text-white font-medium">₪{Math.round(clock.total_interest).toLocaleString('he-IL')}</p>
        </div>
      </div>

      {clock.total_cpi_adjustment > 0 && (
        <div className="mt-2 bg-[#0f1623] rounded p-2 text-xs">
          <p className="text-gray-500">הצמדה למדד</p>
          <p className="text-yellow-400 font-medium">₪{Math.round(clock.total_cpi_adjustment).toLocaleString('he-IL')}</p>
        </div>
      )}
    </div>
  )
}

// ── Detail panel: Chart.js ────────────────────────────────────────────────────

function DetailPanel({ clock }) {
  if (!clock) return null

  const stacked = clock.stacked_bar_data || []
  const cumulative = clock.cumulative_totals_data || []

  const barData = {
    labels: stacked.map(d => `שנה ${d.year}`),
    datasets: [
      {
        label: 'קרן',
        data: stacked.map(d => Number(d.principal)),
        backgroundColor: '#3b82f6',
      },
      {
        label: 'ריבית',
        data: stacked.map(d => Number(d.interest)),
        backgroundColor: '#f59e0b',
      },
      ...(stacked.some(d => Number(d.cpi) > 0) ? [{
        label: 'הצמדה',
        data: stacked.map(d => Number(d.cpi)),
        backgroundColor: '#a78bfa',
      }] : []),
    ],
  }

  const lineData = {
    labels: cumulative.filter((_, i) => i % 12 === 11).map((_, i) => `שנה ${i + 1}`),
    datasets: [
      {
        label: 'סה״כ שולם',
        data: cumulative.filter((_, i) => i % 12 === 11).map(d => Number(d.total_paid_to_date)),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.1)',
        fill: true,
        tension: 0.3,
      },
      {
        label: 'יתרת חוב',
        data: cumulative.filter((_, i) => i % 12 === 11).map(d => Number(d.balance_remaining)),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.1)',
        fill: true,
        tension: 0.3,
      },
    ],
  }

  const chartOptions = {
    responsive: true,
    plugins: { legend: { labels: { color: '#9ca3af' } } },
    scales: {
      x: { ticks: { color: '#6b7280' }, grid: { color: '#1f2937' } },
      y: {
        ticks: {
          color: '#6b7280',
          callback: v => `₪${(v / 1000).toFixed(0)}K`,
        },
        grid: { color: '#1f2937' },
      },
    },
  }

  return (
    <div className="bg-[#1a2333] rounded-xl p-6 mt-6">
      <h3 className="text-white font-semibold text-lg mb-5">פירוט תשלומים שנתי</h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <p className="text-gray-400 text-sm mb-2">פילוח שנתי (קרן / ריבית / הצמדה)</p>
          <Bar data={barData} options={{ ...chartOptions, plugins: { ...chartOptions.plugins, title: { display: false } }, scales: { ...chartOptions.scales, x: { ...chartOptions.scales.x, stacked: true }, y: { ...chartOptions.scales.y, stacked: true } } }} />
        </div>
        <div>
          <p className="text-gray-400 text-sm mb-2">מצטבר: סה״כ שולם לעומת יתרת חוב</p>
          <Line data={lineData} options={chartOptions} />
        </div>
      </div>

      {clock.rate_assumption_notes?.length > 0 && (
        <div className="mt-4 p-3 bg-yellow-900/20 border border-yellow-700/30 rounded text-yellow-300 text-xs">
          {clock.rate_assumption_notes.map((n, i) => <p key={i}>{n}</p>)}
        </div>
      )}
    </div>
  )
}

// ── Main Clocks page ──────────────────────────────────────────────────────────

export default function Clocks() {
  const { applicationId } = useParams()
  const { user } = useAuth()
  const [clocks, setClocks] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!applicationId || !user) return
    user.getToken().then(token =>
      fetch(`${API}/api/calculations/clocks/${applicationId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.json())
        .then(j => {
          const list = j.clocks || []
          setClocks(list)
          if (list.length > 0) setSelected(list[0])
        })
        .catch(() => setError('שגיאה בטעינת השעוני עלות'))
        .finally(() => setLoading(false))
    )
  }, [applicationId, user])

  if (loading) return (
    <div className="min-h-screen bg-[#0f1623] flex items-center justify-center">
      <p className="text-gray-400 text-lg">טוען שעוני עלות...</p>
    </div>
  )

  if (error) return (
    <div className="min-h-screen bg-[#0f1623] flex items-center justify-center">
      <p className="text-red-400">{error}</p>
    </div>
  )

  if (clocks.length === 0) return (
    <div className="min-h-screen bg-[#0f1623] flex items-center justify-center">
      <div className="text-center">
        <p className="text-gray-400 text-lg mb-2">אין שעוני עלות זמינים עדיין</p>
        <p className="text-gray-600 text-sm">המיקס טרם חושב. פנה ליועץ שלך.</p>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-[#0f1623] p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-2">שעוני עלות</h1>
        <p className="text-gray-400 mb-8">השוואת מסלולי משכנתא לבקשה שלך</p>

        <div className={`grid gap-4 ${clocks.length === 1 ? 'grid-cols-1 max-w-xs' : clocks.length === 2 ? 'grid-cols-2' : clocks.length === 3 ? 'grid-cols-3' : clocks.length === 4 ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-2 lg:grid-cols-3 xl:grid-cols-5'}`}>
          {clocks.map(clock => (
            <ClockCard
              key={clock.clock_result_id}
              clock={clock}
              isSelected={selected?.clock_result_id === clock.clock_result_id}
              onClick={() => setSelected(clock)}
            />
          ))}
        </div>

        <DetailPanel clock={selected} />
      </div>
    </div>
  )
}
