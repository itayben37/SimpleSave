import Navbar from '../components/Navbar'

export default function Glossary() {
  return (
    <div className="min-h-screen bg-[#0f1623]" dir="rtl">
      <Navbar />
      <div className="p-6 max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-6">מילון מונחים</h1>
        <p className="text-gray-400">כאן יופיעו מונחי המשכנתא (שלב 6)</p>
      </div>
    </div>
  )
}
