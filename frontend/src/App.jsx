import { useState } from 'react'
import axios from 'axios'
import { API_BASE } from './api'

export default function App() {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const onUpload = async (e) => {
    e.preventDefault()
    if (!file) return
    setLoading(true); setError(''); setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await axios.post(`${API_BASE}/parse`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setResult(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <header>
        <h1 style={{margin: 0, fontSize: 22}}>EDI Translator / Validator</h1>
        <p style={{margin: 0, color: '#6b7280', fontSize: 13}}>Upload X12 EDI → see JSON + validations</p>
      </header>
      <main>
        <div className="card">
          <form onSubmit={onUpload} style={{display:'flex', gap:12, alignItems:'center'}}>
            <input type="file" accept=".edi,.x12,.txt"
              onChange={(e)=> setFile(e.target.files?.[0] || null)} style={{flex:1}}/>
            <button className="btn" disabled={!file || loading}>
              {loading ? 'Parsing...' : 'Upload & Validate'}
            </button>
          </form>
        </div>

        {error && <div className="card error">{error}</div>}

        {result && (
          <section>
            <div className="card">
              <h2 style={{marginTop:0}}>Detection</h2>
              <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))', gap:12}}>
                <Info label="Transaction Set" value={result?.transaction?.set_id || 'Unknown'} />
                <Info label="ISA Present" value={result?.interchange?.ISA ? 'Yes' : 'No'} />
                <Info label="GS Present" value={result?.functional_group?.GS ? 'Yes' : 'No'} />
              </div>
            </div>

            <div className="card">
              <h2 style={{marginTop:0}}>Validation</h2>
              {result.errors?.length ? (
                <ul style={{paddingLeft:18, margin:0}}>
                  {result.errors.map((e, idx) => (
                    <li key={idx} style={{marginBottom:8}}>
                      <div><span className="pill">{e.code}</span> — <b>{e.severity}</b></div>
                      <div style={{fontSize:14}}>{e.message}</div>
                      {e.segment_index !== null && e.segment_index !== undefined && (
                        <div style={{fontSize:12, color:'#6b7280'}}>Segment index: {e.segment_index}</div>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{color:'#047857'}}>No errors found 🎉</p>
              )}
            </div>

            <div className="card">
              <h2 style={{marginTop:0}}>Parsed Segments</h2>
              <table>
                <thead>
                  <tr><th>#</th><th>Tag</th><th>Elements</th></tr>
                </thead>
                <tbody>
                  {result.segments?.map((seg, i) => (
                    <tr key={i}>
                      <td style={{fontFamily:'ui-monospace', fontSize:12}}>{i}</td>
                      <td><b>{seg.tag}</b></td>
                      <td><code>{(seg.elements || []).join(' | ')}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div style={{background:'#f3f4f6', padding:12, borderRadius:12}}>
      <div style={{fontSize:12, color:'#6b7280'}}>{label}</div>
      <div style={{fontWeight:600}}>{value}</div>
    </div>
  )
}
