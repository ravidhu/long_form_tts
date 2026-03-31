const DEFAULT_URL = 'http://localhost:11434'

export interface OllamaModel {
  name: string
  size: number
  modified_at: string
}

export async function checkConnection(url = DEFAULT_URL): Promise<boolean> {
  try {
    const resp = await fetch(`${url}/api/tags`, { signal: AbortSignal.timeout(5000) })
    return resp.ok
  } catch {
    return false
  }
}

export async function listModels(url = DEFAULT_URL): Promise<OllamaModel[]> {
  const resp = await fetch(`${url}/api/tags`, { signal: AbortSignal.timeout(10000) })
  if (!resp.ok) throw new Error(`Ollama returned ${resp.status}`)
  const data = await resp.json()
  return (data.models || []).map((m: OllamaModel) => ({
    name: m.name,
    size: m.size,
    modified_at: m.modified_at
  }))
}

export async function pullModel(
  model: string,
  onProgress: (status: string, percent: number | null) => void,
  url = DEFAULT_URL
): Promise<void> {
  const resp = await fetch(`${url}/api/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, stream: true })
  })

  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`Ollama pull failed (${resp.status}): ${text.slice(0, 200)}`)
  }

  const reader = resp.body?.getReader()
  if (!reader) throw new Error('No response body from Ollama')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const data = JSON.parse(line)
        let percent: number | null = null
        if (data.total && data.completed) {
          percent = Math.round((data.completed / data.total) * 100)
        }
        onProgress(data.status || '', percent)

        if (data.error) {
          throw new Error(data.error)
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }
}

export async function deleteModel(model: string, url = DEFAULT_URL): Promise<void> {
  const resp = await fetch(`${url}/api/delete`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model })
  })
  if (!resp.ok) throw new Error(`Failed to delete model: ${resp.status}`)
}
