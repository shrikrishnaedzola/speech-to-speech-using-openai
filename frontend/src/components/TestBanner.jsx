export default function TestBanner({ apiKeyConfigured }) {
  return (
    <div className="bg-amber-400 px-4 py-2 text-center text-sm font-bold text-amber-950">
      TEST MODE - use dummy data only. Do not share real names, phone numbers, Aadhaar or beneficiary data.
      {apiKeyConfigured === false && (
        <span className="ml-2 font-normal">(OPENAI_API_KEY not set on backend: only Simulate works)</span>
      )}
    </div>
  )
}
