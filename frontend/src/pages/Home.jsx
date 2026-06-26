import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'

export default function Home() {
  const { user } = useAuth()
  const role = user?.role
  const showCTA = !role || role === 'client'

  return (
    <main className="min-h-screen bg-white" dir="rtl">
      <Navbar />

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 py-20 text-center">
        <h1 className="text-4xl font-bold text-slate-900 mb-4 leading-tight">
          המשכנתא שלך, בדרך החכמה
        </h1>
        <p className="text-lg text-slate-600 mb-10 max-w-2xl mx-auto">
          SimpleSave מרכזת את כל מה שצריך לקבלת החלטה מושכלת על משכנתא — בלי פגישות, בלי המתנה, בלי סיבוכים.
        </p>
        {showCTA && (
          <Link
            to="/wizard"
            className="inline-block bg-brand text-white px-8 py-3 rounded-lg font-semibold text-base hover:bg-brand-hover transition-colors"
          >
            התחל עכשיו — משכנתא חדשה
          </Link>
        )}
      </section>

      {/* Feature cards — Phase 2 will expand these */}
      <section className="max-w-5xl mx-auto px-6 pb-20 grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          { title: '5 שעונים חכמים', desc: 'ראה בבירור איזה תמהיל משכנתא מתאים לך' },
          { title: 'ליווי מקצועי', desc: 'יועץ משכנתאות זמין לך בכל שלב בתהליך' },
          { title: 'ניהול מסמכים', desc: 'העלה מסמכים בבטחה ועקוב אחר הסטטוס' },
        ].map((f) => (
          <div key={f.title} className="bg-slate-50 rounded-xl p-6 border border-slate-100">
            <h3 className="font-semibold text-slate-900 mb-2">{f.title}</h3>
            <p className="text-sm text-slate-600">{f.desc}</p>
          </div>
        ))}
      </section>
    </main>
  )
}
